from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.core.management import call_command
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.ai.explainer import explain_cluster
from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.graph.models import RiskCluster
from apps.graph.services import build_director_map, rebuild_clusters
from apps.graph.views import ClusterDetailView, build_graph_data
from apps.owners.models import Director, Directorship, Owner, Ownership
from apps.ingestion.tests.helpers import verified_role


# Russian sample values exercise Unicode source data and legacy-text preservation.
# Application-generated messages and new explanation templates use English.
class ClusterIntegrityTests(TestCase):
    def supplier(self, number, address="А"):
        return Supplier.objects.create(bin=f"{number:012}", name=f"Компания {number}", address=address)

    def initial_cluster(self, size=2):
        suppliers = [self.supplier(number) for number in range(1, size + 1)]
        rebuild_clusters()
        cluster = RiskCluster.objects.get(is_active=True)
        cluster.ai_explanation = "Сохраненное объяснение"
        cluster.explanation_stale = False
        cluster.save(update_fields=["ai_explanation", "explanation_stale"])
        return cluster, suppliers

    def test_repeat_keeps_uuid_text_freshness_and_analysis_time_without_writes(self):
        cluster, _ = self.initial_cluster()
        original = (cluster.uuid, cluster.analysis_fingerprint, cluster.last_analyzed_at, cluster.updated_at)
        with CaptureQueriesContext(connection) as queries:
            summary = rebuild_clusters()
        cluster.refresh_from_db()
        self.assertEqual(summary["unchanged"], 1)
        self.assertEqual((cluster.uuid, cluster.analysis_fingerprint, cluster.last_analyzed_at, cluster.updated_at), original)
        self.assertEqual(cluster.ai_explanation, "Сохраненное объяснение")
        self.assertFalse(cluster.explanation_stale)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("UPDATE ", "INSERT ", "DELETE ")) for q in queries))

    def test_legacy_cluster_keeps_id_and_explanation_on_first_fingerprint(self):
        suppliers = [self.supplier(1), self.supplier(2)]
        cluster = RiskCluster.objects.create(name="Старая группа", ai_explanation="Исходный текст")
        cluster.suppliers.set(suppliers)
        identifier = cluster.uuid
        rebuild_clusters()
        cluster.refresh_from_db()
        self.assertEqual(cluster.uuid, identifier)
        self.assertEqual(cluster.ai_explanation, "Исходный текст")
        self.assertTrue(cluster.explanation_stale)
        self.assertEqual(len(cluster.analysis_fingerprint), 64)

    def test_addition_continues_uuid_and_marks_saved_text_stale(self):
        cluster, suppliers = self.initial_cluster()
        identifier = cluster.uuid
        added = self.supplier(3)
        rebuild_clusters()
        cluster.refresh_from_db()
        self.assertEqual(cluster.uuid, identifier)
        self.assertEqual(set(cluster.suppliers.values_list("pk", flat=True)), {s.pk for s in [*suppliers, added]})
        self.assertEqual(cluster.ai_explanation, "Сохраненное объяснение")
        self.assertTrue(cluster.explanation_stale)
        self.assertEqual(RiskCluster.objects.count(), 1)

    def test_changed_facts_with_identical_membership_invalidate_explanation(self):
        cluster, suppliers = self.initial_cluster()
        original = cluster.analysis_fingerprint
        suppliers[0].phone = "70000000001"
        suppliers[0].save(update_fields=["phone"])
        rebuild_clusters()
        cluster.refresh_from_db()
        self.assertNotEqual(cluster.analysis_fingerprint, original)
        self.assertTrue(cluster.explanation_stale)
        self.assertEqual(cluster.ai_explanation, "Сохраненное объяснение")

    def test_contract_and_owner_changes_are_analysis_inputs(self):
        cluster, suppliers = self.initial_cluster()
        original = cluster.analysis_fingerprint
        Contract.objects.create(supplier=suppliers[0], contract_number="fixture-001",
                                title="Обезличенный договор", amount=Decimal("123.45"),
                                contract_date=timezone.localdate())
        owner = Owner.objects.create(full_name="Тестовый владелец")
        Ownership.objects.create(supplier=suppliers[0], owner=owner)
        rebuild_clusters()
        cluster.refresh_from_db()
        self.assertEqual(cluster.total_contract_amount, Decimal("123.45"))
        self.assertNotEqual(cluster.analysis_fingerprint, original)
        first_change = cluster.analysis_fingerprint
        owner.has_tax_debt = True
        owner.save(update_fields=["has_tax_debt"])
        rebuild_clusters()
        cluster.refresh_from_db()
        self.assertNotEqual(cluster.analysis_fingerprint, first_change)

    def test_removed_connection_retires_group_without_deleting_old_members_or_text(self):
        cluster, suppliers = self.initial_cluster()
        suppliers[0].address = "Б"
        suppliers[0].save(update_fields=["address"])
        rebuild_clusters()
        cluster.refresh_from_db()
        self.assertFalse(cluster.is_active)
        self.assertTrue(cluster.explanation_stale)
        self.assertEqual(cluster.suppliers.count(), 2)
        self.assertEqual(cluster.ai_explanation, "Сохраненное объяснение")
        response = self.client.get(reverse("graph:cluster_list"))
        self.assertEqual(response.context["paginator"].count, 0)
        self.assertEqual(self.client.get(reverse("graph:cluster_detail", args=[cluster.uuid])).status_code, 200)

    def test_merge_continues_oldest_tied_uuid_and_preserves_retired_group(self):
        suppliers = [self.supplier(1), self.supplier(2), self.supplier(3, "Б"), self.supplier(4, "Б")]
        rebuild_clusters()
        first, second = RiskCluster.objects.order_by("pk")
        identifiers = (first.uuid, second.uuid)
        first.ai_explanation, second.ai_explanation = "Группа А", "Группа Б"
        first.save(update_fields=["ai_explanation"])
        second.save(update_fields=["ai_explanation"])
        for supplier in (suppliers[0], suppliers[2]):
            supplier.phone = "70000000000"
            supplier.save(update_fields=["phone"])
        summary = rebuild_clusters()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.uuid, second.uuid), identifiers)
        self.assertTrue(first.is_active)
        self.assertFalse(second.is_active)
        self.assertEqual((first.suppliers.count(), second.suppliers.count()), (4, 2))
        self.assertEqual((first.ai_explanation, second.ai_explanation), ("Группа А", "Группа Б"))
        self.assertEqual(summary["retired"], 1)
        self.assertEqual(rebuild_clusters()["unchanged"], 1)

    def test_split_continues_one_uuid_and_new_uuid_stays_stable(self):
        cluster, suppliers = self.initial_cluster(4)
        for supplier in suppliers[2:]:
            supplier.address = "Б"
            supplier.save(update_fields=["address"])
        rebuild_clusters()
        cluster.refresh_from_db()
        self.assertTrue(cluster.is_active)
        self.assertEqual(set(cluster.suppliers.values_list("pk", flat=True)), {s.pk for s in suppliers[:2]})
        identifiers = set(RiskCluster.objects.filter(is_active=True).values_list("uuid", flat=True))
        self.assertEqual(len(identifiers), 2)
        rebuild_clusters()
        self.assertEqual(set(RiskCluster.objects.filter(is_active=True).values_list("uuid", flat=True)), identifiers)

    def test_exact_inactive_composition_can_be_reactivated(self):
        cluster, suppliers = self.initial_cluster()
        suppliers[0].address = "Б"
        suppliers[0].save(update_fields=["address"])
        rebuild_clusters()
        suppliers[0].address = "А"
        suppliers[0].save(update_fields=["address"])
        rebuild_clusters()
        cluster.refresh_from_db()
        self.assertTrue(cluster.is_active)
        self.assertEqual(RiskCluster.objects.count(), 1)
        self.assertEqual(cluster.ai_explanation, "Сохраненное объяснение")

    def test_failure_rolls_back_prior_group_updates_and_memberships(self):
        cluster, suppliers = self.initial_cluster()
        original = (cluster.name, cluster.analysis_fingerprint, cluster.last_analyzed_at)
        self.supplier(3, "Б")
        self.supplier(4, "Б")
        self.supplier(5)
        with patch("apps.graph.services.RiskCluster.objects.create", side_effect=RuntimeError("fixture failure")):
            with self.assertRaises(RuntimeError):
                rebuild_clusters()
        cluster.refresh_from_db()
        self.assertEqual((cluster.name, cluster.analysis_fingerprint, cluster.last_analyzed_at), original)
        self.assertEqual(set(cluster.suppliers.values_list("pk", flat=True)), {s.pk for s in suppliers})
        self.assertFalse(cluster.explanation_stale)
        self.assertEqual(RiskCluster.objects.count(), 1)

    def test_command_uses_preserving_rebuild(self):
        cluster, _ = self.initial_cluster()
        output = StringIO()
        call_command("build_clusters", stdout=output)
        self.assertIn("unchanged=1", output.getvalue())
        self.assertEqual(RiskCluster.objects.get().uuid, cluster.uuid)

    def test_detail_get_does_not_generate_or_write_even_for_empty_text(self):
        cluster, _ = self.initial_cluster()
        cluster.ai_explanation = ""
        cluster.save(update_fields=["ai_explanation"])
        original_time = cluster.updated_at
        with patch("apps.ai.explainer.explain_cluster", side_effect=AssertionError("GET generated explanation")):
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(reverse("graph:cluster_detail", args=[cluster.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Explanation has not been prepared yet.")
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("UPDATE ", "INSERT ", "DELETE ")) for q in queries))
        cluster.refresh_from_db()
        self.assertEqual(cluster.ai_explanation, "")
        self.assertEqual(cluster.updated_at, original_time)

    def test_invalid_risk_is_controlled_and_bounds_are_clamped(self):
        self.initial_cluster()
        url = reverse("graph:cluster_list")
        self.assertEqual(self.client.get(url, {"risk": "abc"}).status_code, 400)
        self.assertEqual(self.client.get(url, {"risk": "9" * 5000}).status_code, 400)
        self.assertEqual(self.client.get(url, {"risk": -1}).context["paginator"].count, 1)
        self.assertEqual(self.client.get(url, {"risk": 101}).context["paginator"].count, 0)

    def test_get_detects_company_change_before_rebuild_without_persisting(self):
        cluster, suppliers = self.initial_cluster()
        suppliers[0].phone = "70000000001"
        suppliers[0].save(update_fields=["phone"])
        response = self.client.get(reverse("graph:cluster_detail", args=[cluster.uuid]))
        self.assertTrue(response.context["explanation_stale"])
        cluster.refresh_from_db()
        self.assertFalse(cluster.explanation_stale)
        self.assertEqual(cluster.ai_explanation, "Сохраненное объяснение")

    def test_get_detects_contract_change_before_rebuild_and_keeps_database_readonly(self):
        cluster, suppliers = self.initial_cluster()
        Contract.objects.create(supplier=suppliers[0], contract_number="fixture-before-rebuild",
                                title="Fixture", amount=Decimal("12.34"), contract_date=timezone.localdate())
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("graph:cluster_detail", args=[cluster.uuid]))
        self.assertTrue(response.context["explanation_stale"])
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("UPDATE ", "INSERT ", "DELETE ")) for q in queries))
        cluster.refresh_from_db()
        self.assertFalse(cluster.explanation_stale)

    def test_get_freshness_and_queries_are_bounded_for_large_prefetched_group(self):
        director = Director.objects.create(full_name="Тестовый руководитель")
        owner = Owner.objects.create(full_name="Тестовый владелец")
        suppliers = [self.supplier(number) for number in range(1, 21)]
        Directorship.objects.bulk_create([Directorship(supplier=supplier, director=director) for supplier in suppliers])
        Ownership.objects.bulk_create([Ownership(supplier=supplier, owner=owner) for supplier in suppliers])
        rebuild_clusters()
        cluster = RiskCluster.objects.get(is_active=True)
        cluster.ai_explanation = "Сохраненное объяснение"
        cluster.explanation_stale = False
        cluster.save(update_fields=["ai_explanation", "explanation_stale"])
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("graph:cluster_detail", args=[cluster.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["explanation_stale"])
        self.assertLessEqual(len(queries), 12)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("UPDATE ", "INSERT ", "DELETE ")) for q in queries))

    def test_prefetched_graph_has_no_pair_queries(self):
        director = Director.objects.create(full_name="Тестовый руководитель")
        suppliers = [self.supplier(number, "") for number in range(1, 9)]
        for supplier in suppliers:
            verified_role(supplier, director)
        loaded = list(Supplier.objects.prefetch_related("directorships__director", "directorships__person_identity", "directorships__source_observation"))
        with self.assertNumQueries(0):
            graph = build_graph_data(loaded, cluster=RiskCluster(risk_score=35))
        self.assertEqual(len(graph["links"]), 28)
        with self.assertNumQueries(4):
            build_graph_data(suppliers, cluster=RiskCluster(risk_score=35))

    def test_ended_and_future_roles_do_not_connect_current_graph(self):
        today = timezone.localdate()
        suppliers = [self.supplier(1, ""), self.supplier(2, "")]
        director = Director.objects.create(full_name="Тестовый руководитель")
        verified_role(suppliers[0], director, end_date=today)
        verified_role(suppliers[1], director, start_date=today + timedelta(days=1))
        self.assertEqual(rebuild_clusters(as_of=today)["groups"], 0)
        self.assertEqual(build_director_map(suppliers, today), {s.pk: set() for s in suppliers})
        self.assertEqual(build_graph_data(suppliers, cluster=RiskCluster())["links"], [])

    def test_email_case_matches_ui_and_case_only_refresh_does_not_invalidate(self):
        suppliers = [self.supplier(1, ""), self.supplier(2, "")]
        for supplier, email in zip(suppliers, ("contact@example.test", " CONTACT@EXAMPLE.TEST ")):
            supplier.email = email
            supplier.save(update_fields=["email"])
        rebuild_clusters()
        cluster = RiskCluster.objects.get(is_active=True)
        self.assertEqual(build_graph_data(suppliers, cluster=cluster)["links"][0]["type"], "email")
        self.assertIn("contact@example.test", explain_cluster(cluster))
        fingerprint = cluster.analysis_fingerprint
        suppliers[1].email = "contact@example.test"
        suppliers[1].save(update_fields=["email"])
        self.assertEqual(rebuild_clusters()["unchanged"], 1)
        cluster.refresh_from_db()
        self.assertEqual(cluster.analysis_fingerprint, fingerprint)

    def test_unknown_role_dates_do_not_claim_simultaneous_leadership(self):
        suppliers = [self.supplier(1, ""), self.supplier(2, "")]
        director = Director.objects.create(full_name="Тестовый руководитель")
        for supplier in suppliers:
            verified_role(supplier, director)
        rebuild_clusters()
        text = explain_cluster(RiskCluster.objects.get(is_active=True))
        self.assertNotIn("simultaneously", text)
        self.assertIn("leadership periods require confirmation", text)

    def test_linkified_text_escapes_source_html_and_does_not_rewrite_inserted_urls(self):
        supplier = self.supplier(1)
        supplier.name = '<img src=x onerror="alert(1)">'
        supplier.save(update_fields=["name"])
        director = Director.objects.create(full_name="companies")
        Directorship.objects.create(supplier=supplier, director=director)
        html = str(ClusterDetailView._linkify_explanation(f"«{supplier.name}» companies <script>alert(1)</script>", [supplier]))
        self.assertNotIn("<img", html)
        self.assertNotIn("<script", html)
        self.assertIn(f'href="/companies/{supplier.pk}/"', html)
        self.assertEqual(html.count("<a "), 2)


class ClusterStateMigrationTests(TransactionTestCase):
    def test_additive_migration_keeps_legacy_uuid_text_and_membership(self):
        executor = MigrationExecutor(connection)
        executor.migrate([("graph", "0002_alter_connection_connection_type")])
        # New AI migrations depend on graph.0005; omit that future state here.
        old_targets = [node for node in executor.loader.graph.leaf_nodes() if node[0] not in {"graph", "ai"}]
        old_targets.append(("graph", "0002_alter_connection_connection_type"))
        old_apps = executor.loader.project_state(old_targets).apps
        try:
            supplier = old_apps.get_model("companies", "Supplier").objects.create(bin="000000000001", name="Fixture")
            cluster = old_apps.get_model("graph", "RiskCluster").objects.create(name="Legacy", ai_explanation="Saved")
            cluster.suppliers.add(supplier)
            identifier = cluster.uuid
            executor = MigrationExecutor(connection)
            executor.migrate([("graph", "0003_cluster_analysis_state")])
            state = executor.loader.project_state([('graph', '0003_cluster_analysis_state')])
            restored = state.apps.get_model('graph', 'RiskCluster').objects.get(pk=cluster.pk)
            self.assertEqual(restored.uuid, identifier)
            self.assertEqual(restored.ai_explanation, "Saved")
            self.assertEqual(restored.suppliers.count(), 1)
            self.assertTrue(restored.is_active)
            self.assertTrue(restored.explanation_stale)
            self.assertEqual(restored.analysis_fingerprint, "")
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL transaction advisory locks")
class ConcurrentClusterRebuildTests(TransactionTestCase):
    def test_two_connections_create_one_cluster_from_empty_table(self):
        self.assertEqual(RiskCluster.objects.count(), 0)
        Supplier.objects.bulk_create([
            Supplier(bin="000000000001", name="Fixture A", address="Shared fixture office"),
            Supplier(bin="000000000002", name="Fixture B", address="Shared fixture office"),
        ])
        start, lock_attempt = Barrier(2), Barrier(2)

        def worker():
            database = connections["default"]
            lock_queries = []

            def record_lock(execute, sql, params, many, context):
                if "pg_advisory_xact_lock" in sql.lower():
                    lock_queries.append(sql)
                    # Both transactions reach the lock before either can publish a cluster.
                    lock_attempt.wait(timeout=10)
                return execute(sql, params, many, context)

            try:
                database.ensure_connection()
                with database.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '10s'")
                    cursor.execute("SET statement_timeout = '20s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    backend_pid = cursor.fetchone()[0]
                start.wait(timeout=10)
                with database.execute_wrapper(record_lock):
                    summary = rebuild_clusters()
                identifier = RiskCluster.objects.get(is_active=True).uuid
                return summary, identifier, backend_pid, len(lock_queries)
            finally:
                # Django connections are thread-local; close every connection owned by this worker.
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(worker) for _ in range(2)]
            results = [future.result(timeout=40) for future in futures]
        self.assertEqual(len({result[2] for result in results}), 2)
        self.assertEqual([result[3] for result in results], [1, 1])
        self.assertEqual(sum(result[0]["created"] for result in results), 1)
        self.assertEqual(sum(result[0]["unchanged"] for result in results), 1)
        self.assertEqual(RiskCluster.objects.count(), 1)
        cluster = RiskCluster.objects.get(is_active=True)
        self.assertEqual(cluster.suppliers.count(), 2)
        self.assertEqual({result[1] for result in results}, {cluster.uuid})
