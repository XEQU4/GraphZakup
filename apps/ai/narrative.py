"""Bounded prose over saved facts; these checks are not a semantic proof."""
import re
from decimal import Decimal, InvalidOperation

from .presentation import wording_variants


class NarrativeValidationError(ValueError):
    """Safe validation codes only; never include generated or source content."""


_GUIDANCE = {
    'shared_address': ('An address match is weak evidence and can come from a shared office or registration service.',
                       'Find out whether this is a shared office or registration service and who maintains the address.'),
    'shared_phone': ('A matching phone is weak evidence and can come from a common administrator or service provider.',
                     'Find out who answers or maintains this phone and whether it is a common service provider.'),
    'shared_email': ('A matching email is weak evidence and can come from a common administrator or service provider.',
                     'Find out who maintains this email and whether it is a common administrative service.'),
    'shared_director': ('A verified shared director makes decision-making authority worth checking. Tender participation still needs separate records.',
                        'Check the director\'s authority over tender decisions and whether the firms were bidders in the same lots. Identity is already confirmed.'),
    'shared_owner': ('A verified shared owner makes company control worth reviewing. Tender participation still needs separate records.',
                     'Check company control at the relevant dates and whether these firms competed in the same lots. Identity is already confirmed.'),
    'mixed_person_roles': ('A verified person has different recorded roles across firms; the dates and scope of authority need attention.',
                           'Check the dates and scope of the recorded ownership and management authority, then relevant tender participation.'),
    'company_arrears': ('This dated result concerns a company. It does not establish owner debt or an undated current balance.',
                       'Obtain a dated company arrears result to verify the present balance; keep person checks separate.'),
    'company_zero_arrears': ('Zero applies to the dated company result; it is not overall clearance of the firm or a person.',
                            'Check whether a newer dated company result is available if a current assessment is required.'),
    'stored_contract_summary': ('Contract totals describe activity, not losses or tender competition.',
                                'Obtain lot participants, bids and outcomes before assessing competition or bidding patterns.'),
}


def company_tokens(analysis):
    """Stable local aliases; the provider never receives names or identifiers."""
    nodes = getattr(analysis, 'inputs', {}).get('graph', {}).get('nodes', [])
    companies = sorted((node for node in nodes if node.get('kind') == 'company'),
                       key=lambda node: node['company_id'])
    return {f'C{index}': node for index, node in enumerate(companies, 1)}


def finding_context(analysis, finding):
    aliases = {node['company_id']: token for token, node in company_tokens(analysis).items()}
    result = {'finding_id': finding['id'], 'code': finding.get('code', 'saved_finding'),
            'companies': [aliases[pk] for pk in finding.get('company_ids', []) if pk in aliases],
            'variants': wording_variants(analysis, finding),
            'limitations': finding.get('limitations', [])}
    if finding.get('code') in _GUIDANCE:
        result['interpretation'], result['follow_up'] = _GUIDANCE[finding['code']]
    if finding.get('code') in {'shared_director', 'shared_owner', 'mixed_person_roles'}:
        references = {item['id'] for item in finding.get('evidence', []) if item['kind'] == 'graph_edge'}
        edges = [edge for edge in getattr(analysis, 'inputs', {}).get('graph', {}).get('links', [])
                 if edge['id'] in references]
        result['role_dates_complete'] = bool(edges) and all(edge.get('valid_from') and edge.get('valid_until') for edge in edges)
    if finding.get('code') in {'company_arrears', 'company_zero_arrears'}:
        checks = getattr(analysis, 'inputs', {}).get('company_checks', [])
        result['check_status'] = next((item['status'] for item in checks
            if item['company_id'] in finding.get('company_ids', [])), 'unknown')
    return result


def normalize_inline_citations(value, ids):
    """Remove redundant known citation badges, preserving their structured evidence.

    No claim, number or unknown reference is repaired. Small local models can repeat
    structured finding IDs parenthetically; the reference already exists beside text.
    """
    if not isinstance(value, dict) or not isinstance(value.get('narrative'), dict):
        return value
    for key in ('paragraphs', 'checks'):
        items = value['narrative'].get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get('text'), str):
                continue
            references = item.get('finding_ids')
            if not isinstance(references, list):
                continue
            permitted = {pk for pk in references if isinstance(pk, str) and pk in ids}
            pattern = r'\s*\(\s*(?:(?:finding(?:_id)?|evidence|source|id)\s*:?\s*)?(f-[0-9a-f]+)\s*\)'
            item['text'] = re.sub(pattern, lambda match: '' if match.group(1) in permitted else match.group(0),
                                  item['text'], flags=re.I)
            trailing = r',?\s+(?:per\s+)?(?:follow-up\s+for|finding(?:_id)?\s*[: ]+)\s*(f-[0-9a-f]+)(?=[.!?]?$)'
            item['text'] = re.sub(trailing, lambda match: '' if match.group(1) in permitted else match.group(0),
                                  item['text'], flags=re.I)
    return value


def normalize_company_aliases(value, context):
    """Wrap bare known aliases only within the scope of cited saved companies."""
    by_id = {fact['finding_id']: fact for fact in context}
    if not isinstance(value, dict) or not isinstance(value.get('narrative'), dict):
        return value
    for key in ('paragraphs', 'checks'):
        items = value['narrative'].get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get('text'), str):
                continue
            references = item.get('finding_ids')
            if not isinstance(references, list):
                continue
            permitted = {alias for reference in references if isinstance(reference, str) and reference in by_id
                         for alias in by_id[reference].get('companies', [])}
            item['text'] = re.sub(r'(?<![\w{])C[1-9]\d*(?![\w}])',
                lambda match: '{{' + match.group(0) + '}}' if match.group(0) in permitted else match.group(0),
                item['text'])
    return value


_TOKEN = re.compile(r'\{\{(C[1-9]\d*)\}\}')
_NUMBER = re.compile(r'(?<![\w])-?\d+(?:[,.]\d+)*(?:-\d+)*')
_WORD_NUMBERS = {'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
                 'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
                 'ten': '10', 'eleven': '11', 'twelve': '12', 'thirteen': '13',
                 'fourteen': '14', 'fifteen': '15', 'sixteen': '16', 'seventeen': '17',
                 'eighteen': '18', 'nineteen': '19', 'twenty': '20'}
_WORDS_NUMBER = re.compile(r'\b(' + '|'.join(_WORD_NUMBERS) + r')\b', re.I)
_NEGATION = re.compile(r'\b(?:no|not|never|cannot|can\s+not|doesn[’\']t|don[’\']t|without|unavailable|missing|lacks?|unknown|unverified|unconfirmed|unproven)\b', re.I)
_FOLLOW_UP = re.compile(r'\b(?:check|confirm|verify|review|obtain|compare|establish|determine|inspect|request|investigate|assess|clarify)\b', re.I)


def _numbers(text):
    text = _TOKEN.sub('', text)
    def canonical(value):
        if ',' in value and not re.fullmatch(r'-?\d{1,3}(?:,\d{3})+(?:\.\d+)?', value):
            # A malformed grouping is not equivalent to removing punctuation.
            return value
        cleaned = value.replace(',', '')
        try:
            # Decimal construction/equality is exact, including omitted .00 and large amounts.
            # ISO dates keep their whole string; do not treat them as arithmetic or year parts.
            return Decimal(cleaned)
        except InvalidOperation:
            return value
    return {canonical(value) for value in _NUMBER.findall(text)} | {
        Decimal(_WORD_NUMBERS[value.lower()]) for value in _WORDS_NUMBER.findall(text)}


def _denied_by_contrast(sentence, match):
    """Only the contrasted term is denied, not an earlier affirmative claim."""
    return bool(match and re.search(r'\brather\s+than\s+(?:\w+\s+){0,4}$',
                                   sentence[:match.start()], re.I))


def _clauses(text):
    """Preserve coordinated noun subjects with their shared negative predicate."""
    noun = r'(?:ownership|management|directorship|owners?|directors?|roles?|control)'
    result = []
    for base in re.split(r'(?<=[.!?;])\s+|\s+(?:but|while|although)\s+', text, flags=re.I):
        start = 0
        for match in re.finditer(r'\s+and\s+', base, re.I):
            left, right = base[start:match.start()], base[match.end():]
            shared_subject = (re.search(r'\b' + noun + r'\s*$', left, re.I)
                and re.match(noun + r'\b', right, re.I)
                and re.match(r'(?:\w+\s+){0,5}(?:remain(?:s)?|is|are|was|were|has|have)\s+'
                             r'(?:\w+\s+){0,3}(?:unverified|unknown|unconfirmed|unproven|not)\b', right, re.I))
            if shared_subject:
                continue
            result.append(base[start:match.start()])
            start = match.end()
        result.append(base[start:])
    return result


def _claim_denied(sentence, match):
    """A missing-role qualifier elsewhere cannot deny a coordination assertion."""
    before, after = sentence[:match.start()], sentence[match.end():]
    return bool(re.search(r'\b(?:no|not|never|cannot|without)\s+(?:\w+\s+){0,5}$', before, re.I)
        or re.match(r'^\s+(?:\w+\s+){0,2}(?:(?:is|are|was|were|remain(?:s)?|has|have)\s+'
                    r'(?:unverified|unknown|unconfirmed|unproven|not)\b|'
                    r'(?:cannot|can\s+not)\s+(?:be\s+)?(?:established|assessed|confirmed)\b)', after, re.I))


def _contact_administration(sentence, match, codes):
    if not match or match.group(0) != 'managed' or not codes & {'shared_address', 'shared_phone', 'shared_email'}:
        return False
    # A shared inbox/service can be administered without proving a company officer role.
    return bool(re.search(r'\b(?:email|e-mail|phone|contact|address|inbox|mailbox|service)\s+'
        r'(?:is|are|was|were|may|could|might|can)(?:\s+(?:be|being|have|been|not)){0,3}\s+$',
        sentence[:match.start()]))


def _check_claims(text, facts, *, check=False):
    """Reject obvious contradictions; legitimate negation and questions survive."""
    codes = {fact['code'] for fact in facts}
    for sentence in _clauses(text):
        negative = bool(_NEGATION.search(sentence))
        follow_up = check and bool(_FOLLOW_UP.search(sentence))
        lowered = sentence.lower()
        # These concepts may be denied or requested for verification, never reported.
        accusation = re.search(r'\b(?:collu\w*|cartel\w*|corrupt\w*|fraud\w*|criminal\w*|illegal|violation\w*|rigg\w*|dishonest|guilty|coordinat\w*)\b', lowered)
        if accusation:
            if not (_claim_denied(lowered, accusation) or follow_up):
                raise NarrativeValidationError('output_claim_unsupported')
        if re.search(r'\b(?:high|low|medium|moderate|severe|elevated)\s+(?:risk|suspicion)\b|\b(?:risk|review.priority)\s+(?:score|rating|index)\b|\d\s*/\s*100|%|\bpercent(?:age)?\b', lowered):
            raise NarrativeValidationError('output_score_in_prose')
        ownership = re.search(r'\b(?:owner\w*|ownership|owns|owned|beneficial|common\s+control|controlled|subsidiar\w*|parent\s+company)\b', lowered)
        if ownership:
            if not codes & {'shared_owner', 'mixed_person_roles'} and not (negative or follow_up or _denied_by_contrast(lowered, ownership)):
                raise NarrativeValidationError('output_role_unsupported')
        if re.search(r'\b(?:owner\w*|ownership|director\w*|management|managed)\b', lowered):
            incomplete = any(not fact.get('role_dates_complete', False)
                             for fact in facts if fact['code'] in {'shared_director', 'shared_owner', 'mixed_person_roles'})
            if incomplete and re.search(r'\b(?:currently|current|simultaneous\w*|concurrent\w*|presently)\b', lowered) and not (negative or follow_up):
                raise NarrativeValidationError('output_role_period_unsupported')
            if re.search(r'\b(?:up\s+to|until|ends?|ended|expires?|expires?|through)\s+\d{4}-\d{2}-\d{2}\b', lowered):
                raise NarrativeValidationError('output_role_end_invented')
        management = re.search(r'\b(?:director\w*|management|managed)\b', lowered)
        if management:
            if not codes & {'shared_director', 'mixed_person_roles'} and not (negative or follow_up or
                    _denied_by_contrast(lowered, management) or _contact_administration(lowered, management, codes)):
                raise NarrativeValidationError('output_role_unsupported')
        authority = re.search(r'\b(?:decision[- ]making\s+authority|authority\s+(?:over|for|to)\s+'
                              r'(?:\w+\s+){0,3}(?:tender\w*|bid\w*)|control\w*\s+'
                              r'(?:\w+\s+){0,3}(?:tender\w*|bidding|bids)|'
                              r'decid\w*\s+(?:\w+\s+){0,3}(?:tender\w*|bids))\b', lowered)
        if authority:
            # A verified officer role does not establish tender decision authority.
            uncertain = bool(re.search(r'\b(?:whether|if)\s+(?:\w+\s+){0,6}$',
                                       lowered[:authority.start()])
                or re.match(r'^\s+(?:\w+\s+){0,2}(?:(?:is|remains?)\s+)?(?:worth\s+checking|needs?\s+'
                            r'(?:checking|verification)|requires?\s+verification)\b',
                            lowered[authority.end():]))
            if not (_claim_denied(lowered, authority) or follow_up or uncertain):
                raise NarrativeValidationError('output_authority_unsupported')
        if re.search(r'\b(?:debt\w*|arrears|owes|owed)\b', lowered):
            if not codes & {'company_arrears', 'company_zero_arrears'} and not (negative or follow_up):
                raise NarrativeValidationError('output_debt_unsupported')
            if re.search(r'\b(?:owner\w*|person\w*|director\w*)\b', lowered) and not (negative or follow_up):
                raise NarrativeValidationError('output_owner_debt_unsupported')
            stale = any(fact.get('check_status') not in {'fresh', 'retained_fresh'}
                        for fact in facts if fact['code'] in {'company_arrears', 'company_zero_arrears'})
            if stale and re.search(r'\b(?:current\w*|present\w*|today|now|owes|is\s+in\s+debt|has\s+(?:tax\s+)?(?:debts?|arrears))\b', lowered) and not (negative or follow_up):
                raise NarrativeValidationError('output_debt_period_unsupported')
        if re.search(r'\b(?:bankrupt\w*|convict\w*|blacklist\w*|criminal\s+record|court\s+(?:case|finding|decision))\b', lowered):
            if not (negative or follow_up):
                raise NarrativeValidationError('output_history_unsupported')
        # Shared contacts must not become proven affiliation or tender competition.
        if re.search(r'\b(?:affiliated|affiliation|competed|participated|bid\s+against|same\s+tenders|same\s+lots)\b', lowered):
            conditional = bool(re.search(r'\b(?:whether|if|could|may|might|potential|possible|need\w*|require\w*)\b', lowered))
            if not (negative or follow_up or conditional):
                raise NarrativeValidationError('output_behaviour_unsupported')


def validate_narrative(value, ids, context):
    """Shape, evidence, alias, numerical and contradiction checks, not entailment."""
    if not isinstance(value, dict) or set(value) != {'paragraphs', 'checks'}:
        raise NarrativeValidationError('output_narrative_schema_invalid')
    by_id = {fact['finding_id']: fact for fact in context}
    for name, max_chars, max_words in [('paragraphs', 600, 100), ('checks', 360, 50)]:
        items = value[name]
        if not isinstance(items, list) or not 1 <= len(items) <= 2:
            raise NarrativeValidationError('output_narrative_length_invalid')
        seen, word_count = set(), 0
        for item in items:
            if not isinstance(item, dict) or set(item) != {'text', 'finding_ids'}:
                raise NarrativeValidationError('output_narrative_schema_invalid')
            text, references = item['text'], item['finding_ids']
            if not isinstance(text, str) or not 20 <= len(text.strip()) <= max_chars or text != text.strip():
                raise NarrativeValidationError('output_narrative_length_invalid')
            if text.casefold() in seen:
                raise NarrativeValidationError('output_narrative_duplicate')
            seen.add(text.casefold())
            word_count += len(text.split())
            if (not isinstance(references, list) or not references or len(references) > len(ids)
                    or any(not isinstance(pk, str) or pk not in ids or pk not in by_id for pk in references)
                    or len(set(references)) != len(references)):
                raise NarrativeValidationError('output_narrative_evidence_invalid')
            facts = [by_id[pk] for pk in references]
            aliases = {alias for fact in facts for alias in fact.get('companies', [])}
            tokens = _TOKEN.findall(text)
            if any(token not in aliases for token in tokens):
                raise NarrativeValidationError('output_narrative_alias_invalid')
            plain = _TOKEN.sub('', text)
            if (re.search(r'https?://|www\.|<|>|\[[^\]]*\]\(|[`#*]|[{}]|\bC\d+\b|\bf-[0-9a-f]+\b|\bvariant\s+\d', plain, re.I)
                    or any(ord(char) < 32 or ord(char) == 127 for char in plain)):
                raise NarrativeValidationError('output_narrative_markup_invalid')
            allowed_numbers = {Decimal(1)}
            for fact in facts:
                for wording in fact['variants'] + fact.get('limitations', []):
                    allowed_numbers |= _numbers(wording)
            if not _numbers(text) <= allowed_numbers:
                raise NarrativeValidationError('output_narrative_number_unsupported')
            _check_claims(text, facts, check=name == 'checks')
        if word_count > max_words:
            raise NarrativeValidationError('output_narrative_length_invalid')
    primary = context[0] if context else None
    if primary:
        first = value['paragraphs'][0]
        if primary['finding_id'] not in first['finding_ids']:
            raise NarrativeValidationError('output_narrative_primary_missing')
    return value
