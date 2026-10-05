from datetime import date, timedelta
from decimal import Decimal
from html.parser import HTMLParser

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.graph.models import RiskCluster
from apps.owners.models import Director, Directorship


class FragmentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.attributes = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)


class PublicViewRegressionTests(TestCase):
    def setUp(self):
        self.payload = '<img src=x onerror=alert(1)>'
        self.supplier = Supplier.objects.create(bin='000000000001', name=self.payload)
        self.director = Director.objects.create(full_name=self.payload)
        Directorship.objects.create(supplier=self.supplier, director=self.director)

    def assert_safe_fragment(self, fragment):
        parser = FragmentParser()
        parser.feed(fragment)
        self.assertNotIn('img', parser.tags)
        self.assertNotIn('script', parser.tags)
        self.assertFalse(any(name.lower().startswith('on') for name, _ in parser.attributes))
        self.assertIn('&lt;img', fragment)

    def test_director_text_is_escaped_in_company_search(self):
        response = self.client.get(reverse('companies:list'), {'format': 'json'})
        self.assertEqual(response.status_code, 200)
        self.assert_safe_fragment(response.json()['results'][0]['director_html'])

    def test_company_text_is_escaped_in_director_search(self):
        response = self.client.get(reverse('owners:list'), {'format': 'json'})
        self.assertEqual(response.status_code, 200)
        self.assert_safe_fragment(response.json()['results'][0]['companies_html'])

    def test_contract_number_is_escaped_with_and_without_external_link(self):
        for gos_id in (None, 123):
            with self.subTest(gos_id=gos_id):
                Contract.objects.all().delete()
                Contract.objects.create(
                    supplier=self.supplier, contract_number=self.payload,
                    contract_gos_id=gos_id, title='Synthetic contract',
                    amount=Decimal('1234567890.12'), contract_date=date(2026, 1, 1),
                )
                response = self.client.get(reverse('dashboard:index'), {'format': 'json'})
                self.assertEqual(response.status_code, 200)
                self.assert_safe_fragment(response.json()['results'][0]['number_html'])

    def test_related_company_count_deduplicates_all_evidence_types(self):
        self.supplier.address = 'Synthetic office'
        self.supplier.phone = '+70000000000'
        self.supplier.email = 'synthetic@example.test'
        self.supplier.save()
        related = Supplier.objects.create(
            bin='000000000002', name='Related', address=self.supplier.address,
            phone=self.supplier.phone, email=self.supplier.email.upper(),
        )
        Directorship.objects.create(supplier=related, director=self.director)
        response = self.client.get(reverse('companies:detail', args=[self.supplier.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_related'], 1)

    def test_finished_and_future_roles_are_not_current_links(self):
        today = timezone.localdate()
        for number, dates in enumerate((
            {'end_date': today - timedelta(days=1)},
            {'start_date': today + timedelta(days=1)},
        ), 2):
            related = Supplier.objects.create(bin=f'{number:012d}', name=f'Past or future {number}')
            Directorship.objects.create(supplier=related, director=self.director, **dates)
        response = self.client.get(reverse('companies:detail', args=[self.supplier.pk]))
        self.assertEqual(response.context['total_related'], 0)

    def test_director_pages_count_only_current_companies(self):
        finished = Supplier.objects.create(bin='000000000002', name='Finished')
        Directorship.objects.create(supplier=finished, director=self.director, end_date=timezone.localdate())
        search = self.client.get(reverse('owners:list'), {'format': 'json'})
        self.assertEqual(search.json()['results'][0]['companies_count'], 1)
        self.assertNotIn('Finished', search.json()['results'][0]['companies_html'])
        detail = self.client.get(reverse('owners:detail', args=[self.director.pk]))
        self.assertEqual(list(detail.context['companies']), [self.supplier])

    def test_search_join_does_not_multiply_director_company_count(self):
        self.supplier.name = 'Matching one'
        self.supplier.save()
        second = Supplier.objects.create(bin='000000000002', name='Matching two')
        Directorship.objects.create(supplier=second, director=self.director)
        response = self.client.get(reverse('owners:list'), {'format': 'json', 'q': 'Matching'})
        self.assertEqual(response.json()['results'][0]['companies_count'], 2)

    def test_legacy_unsafe_website_is_not_rendered_as_a_link(self):
        self.supplier.website = 'javascript:alert(1)'
        self.supplier.save()
        response = self.client.get(reverse('companies:detail', args=[self.supplier.pk]))
        self.assertEqual(response.context['website_url'], '')
        self.assertNotContains(response, 'javascript:')
        self.supplier.website = 'https://example.test/company'
        self.supplier.save()
        response = self.client.get(reverse('companies:detail', args=[self.supplier.pk]))
        self.assertContains(response, 'href="https://example.test/company"')

    def test_archived_clusters_do_not_contribute_to_current_risk_or_dashboard(self):
        active = RiskCluster.objects.create(name='Current', risk_score=50, total_contract_amount=Decimal('10.00'))
        archived = RiskCluster.objects.create(name='Archived', risk_score=100, total_contract_amount=Decimal('99.00'), is_active=False)
        active.suppliers.add(self.supplier)
        archived.suppliers.add(self.supplier)
        detail = self.client.get(reverse('companies:detail', args=[self.supplier.pk]))
        self.assertEqual(detail.context['avg_risk_score'], 50)
        self.assertEqual(list(detail.context['clusters']), [active])
        search = self.client.get(reverse('companies:list'), {'format': 'json'})
        self.assertIn('50/100', search.json()['results'][0]['badge_html'])
        dashboard = self.client.get(reverse('dashboard:index'))
        self.assertEqual(dashboard.context['cluster_count'], 1)
        self.assertEqual(dashboard.context['money_at_risk'], Decimal('10.00'))
        self.assertEqual(list(dashboard.context['top_clusters']), [active])
        self.assertEqual(dashboard.context['short_suppliers'][0].primary_cluster, active)
