"""Helper utilities for working with paper node structures."""

from __future__ import annotations

import json
import random
import re
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

from django.db import transaction

from .models import ExamNode, Paper
from core.models import ExtractorUserBox, ExtractorPaper


class RandomizationPoolError(Exception):
    """Raised when the captured snapshot pool cannot satisfy randomization."""

    pass


def _serialize_content(content):
    if isinstance(content, (list, dict)):
        return json.loads(json.dumps(content))
    return content


def _natural_key(value: str | None) -> list:
    text = (value or '').strip()
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r'(\d+)', text)]


def build_node_tree(paper: Paper) -> Tuple[List[Dict[str, object]], Dict[str, int]]:
    nodes_qs = list(
        ExamNode.objects.filter(paper=paper)
        .select_related('parent')
        .order_by('order_index')
    )

    stats = {
        'total': len(nodes_qs),
        'questions': 0,
        'tables': 0,
        'images': 0,
        'instructions': 0,
    }

    children_map: Dict[str, List[ExamNode]] = defaultdict(list)
    node_lookup: Dict[str, ExamNode] = {}

    for node in nodes_qs:
        node_id = str(node.id)
        node_lookup[node_id] = node
        if node.parent_id:
            children_map[str(node.parent_id)].append(node)

        if node.node_type == 'question':
            stats['questions'] += 1
        elif node.node_type == 'table':
            stats['tables'] += 1
        elif node.node_type == 'image':
            stats['images'] += 1
        elif node.node_type == 'instruction':
            stats['instructions'] += 1

    def serialize(node: ExamNode, parent_number: str | None = None) -> Dict[str, object]:
        payload = {
            'id': str(node.id),
            'node_type': node.node_type,
            'number': node.number,
            'text': node.text,
            'marks': node.marks,
            'content': _serialize_content(node.content),
            'children': [],
            'order_index': node.order_index,
            'parent_number': parent_number,
        }
        for child in children_map[str(node.id)]:
            payload['children'].append(serialize(child, node.number))
        return payload

    tree = [serialize(node, None) for node in nodes_qs if node.parent_id is None]
    return tree, stats


def clone_randomized_structure(
    original_paper: Paper,
    target_paper: Paper,
    shuffle_questions: bool = True,
) -> int:
    """Clone node structure from original paper to target paper.

    Returns the total marks calculated for the cloned paper.
    """

    target_paper.nodes.all().delete()

    nodes_qs = list(
        ExamNode.objects.filter(paper=original_paper)
        .select_related('parent')
        .order_by('order_index')
    )

    children_map: Dict[str, List[ExamNode]] = defaultdict(list)
    root_nodes: List[ExamNode] = []
    question_roots: List[ExamNode] = []
    meta_number_map: Dict[str, str] = {}

    for node in nodes_qs:
        node_id = str(node.id)
        if node.parent_id:
            children_map[str(node.parent_id)].append(node)
        else:
            root_nodes.append(node)
            if node.node_type == 'question':
                question_roots.append(node)

    # Shuffle question order if desired
    if shuffle_questions and len(question_roots) > 1:
        random.shuffle(question_roots)

    # Assign new sequential numbering to questions
    for index, node in enumerate(question_roots, start=1):
        meta_number_map[str(node.id)] = str(index)

    cover_nodes = [node for node in root_nodes if node.node_type != 'question']
    traversal_order = cover_nodes + question_roots

    order_counter = 1
    total_marks = 0

    def clone_node(node: ExamNode, parent: ExamNode | None = None) -> ExamNode:
        nonlocal order_counter, total_marks
        number = meta_number_map.get(str(node.id), node.number)
        cloned = ExamNode.objects.create(
            paper=target_paper,
            parent=parent,
            node_type=node.node_type,
            number=number,
            text=node.text,
            marks=node.marks,
            content=_serialize_content(node.content),
            order_index=order_counter,
        )
        order_counter += 1
        if cloned.node_type == 'question':
            try:
                total_marks += int(cloned.marks or 0)
            except (TypeError, ValueError):
                pass
        for child in children_map.get(str(node.id), []):
            clone_node(child, cloned)
        return cloned

    with transaction.atomic():
        for root in traversal_order:
            clone_node(root, None)

    return total_marks


def _normalize_box_type(qtype: str | None) -> str:
    mapping = {
        'question': 'question',
        'question_part': 'question',
        'heading': 'heading',
        'case_study': 'case_study',
        'instruction': 'instruction',
        'cover_page': 'cover_page',
        'rubric': 'instruction',
        'question_header': 'heading',
    }
    return mapping.get((qtype or '').strip().lower(), 'question')


def _normalize_node_type(node_dict: Dict[str, object]) -> str:
    node_type = (node_dict.get('node_type') or '').lower()
    number = node_dict.get('number')
    content = node_dict.get('content') or []

    if node_type == 'question':
        return 'question'
    if node_type in {'table', 'image'}:
        return node_type
    if node_type in {'instruction', 'text'}:
        # Detect case study blocks
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and (item.get('type') or '').lower() == 'case_study':
                    return 'case_study'
        return 'heading' if number else 'instruction'
    return 'instruction'


def _box_payload(box: ExtractorUserBox) -> Tuple[List[dict], str, str]:
    raw = box.content
    payload: List[dict] = []
    if raw:
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            parsed = None
        if isinstance(parsed, dict):
            if isinstance(parsed.get('items'), list):
                payload = parsed['items']
            elif isinstance(parsed.get('content'), list):
                payload = parsed['content']
        elif isinstance(parsed, list):
            payload = parsed

    text_value = ''
    for item in payload:
        if not isinstance(item, dict):
            continue
        item_type = (item.get('type') or '').lower()
        if item_type in {'text', 'question_text', 'instruction', 'case_study', 'heading'}:
            text_value = item.get('text') or text_value
            if text_value:
                break

    marks_value = box.marks or ''
    return payload, text_value, marks_value




def collect_randomization_pool(module_name: str | None, module_number: str | None, base_extractor: ExtractorPaper | None = None):
    """Return pool candidates grouped by question/parent for the given module filters."""
    print(f"[DEBUG] collect_randomization_pool called with module_name='{module_name}', module_number='{module_number}', base_extractor={base_extractor}")
    module_filter = (module_name or '').strip()
    module_letter_raw = (module_number or '').strip()
    module_letter = ''.join(ch for ch in module_letter_raw if ch.isalpha()) or module_letter_raw

    print(f"[DEBUG] module_filter='{module_filter}', module_letter='{module_letter}'")
    if not module_filter:
        print("[ERROR] Module name is required for randomization.")
        raise RandomizationPoolError("Module name is required for randomization.")
    if not module_letter:
        print("[ERROR] Module number/letter is required for randomization.")
        raise RandomizationPoolError("Module number/letter is required for randomization.")

    pool_qs = ExtractorUserBox.objects.filter(paper__isnull=False)
    print(f"[DEBUG] Initial pool_qs count: {pool_qs.count()}")
    pool_qs = pool_qs.filter(paper__module_name__iexact=module_filter)
    print(f"[DEBUG] After module_name filter: {pool_qs.count()}")
    pool_qs = pool_qs.exclude(paper__paper_letter__isnull=True).exclude(paper__paper_letter__exact='')
    print(f"[DEBUG] After exclude paper_letter null/empty: {pool_qs.count()}")
    pool_qs = pool_qs.filter(paper__paper_letter__iexact=module_letter)
    print(f"[DEBUG] After paper_letter filter: {pool_qs.count()}")

    pool_list = list(pool_qs)
    print(f"[DEBUG] Final pool_list length: {len(pool_list)}")

    if base_extractor is not None:
        base_boxes = list(base_extractor.user_boxes.all())
        base_letter = (getattr(base_extractor, 'paper_letter', '') or '').strip()
        base_letter_norm = ''.join(ch for ch in base_letter if ch.isalpha()) or base_letter
        print(f"[DEBUG] base_extractor paper_letter='{base_letter}', normalized='{base_letter_norm}'")
        if base_letter_norm.lower() == module_letter.lower():
            existing_ids = {getattr(box, 'id', None) for box in pool_list}
            added = 0
            for box in base_boxes:
                if getattr(box, 'id', None) not in existing_ids:
                    pool_list.append(box)
                    added += 1
            print(f"[DEBUG] Added {added} boxes from base_extractor")

    pool_by_number: Dict[Tuple[str, str], List[ExtractorUserBox]] = defaultdict(list)
    pool_by_parent: Dict[Tuple[str, str], List[ExtractorUserBox]] = defaultdict(list)

    for box in pool_list:
        type_key = _normalize_box_type(box.qtype)
        # normalize keys: some extractor boxes use '0' for empty/cover markers
        number_key = (box.question_number or '').strip()
        parent_key = (box.parent_number or '').strip()
        if number_key == '0':
            number_key = ''
        if parent_key == '0':
            parent_key = ''
        pool_by_number[(number_key, type_key)].append(box)
        if parent_key:
            pool_by_parent[(parent_key, type_key)].append(box)

    print(f"[DEBUG] pool_by_number keys: {list(pool_by_number.keys())}")
    print(f"[DEBUG] pool_by_parent keys: {list(pool_by_parent.keys())}")

    return {
        'pool_list': pool_list,
        'pool_by_number': pool_by_number,
        'pool_by_parent': pool_by_parent,
        'module_filter': module_filter,
        'module_number': module_letter,
    }


def get_pool_summary(original_paper: Paper | None, module_name: str | None, module_number: str | None, base_extractor: ExtractorPaper | None = None):
    """Build a summary of pool entries and coverage for the supplied paper blueprint."""
    module_filter = (module_name or '').strip()
    module_letter = (module_number or '').strip()

    if original_paper is None:
        return {
            'pool_entries': [],
            'pool_size': 0,
            'module_filter': module_filter,
            'module_number': module_letter,
            'coverage': [],
        }

    try:
        pool_info = collect_randomization_pool(module_name, module_number, base_extractor)
    except RandomizationPoolError:
        pool_info = {
            'pool_list': [],
            'pool_by_number': defaultdict(list),
            'pool_by_parent': defaultdict(list),
            'module_filter': module_filter,
            'module_number': module_letter,
        }

    blueprint, _ = build_node_tree(original_paper)
    coverage: List[Dict[str, object]] = []

    def walk(nodes: List[Dict[str, object]]):
        for node in nodes:
            type_key = _normalize_node_type(node)
            number_key = (node.get('number') or '').strip()
            matches = len(pool_info['pool_by_number'].get((number_key, type_key), []))
            coverage.append({
                'id': node.get('id'),
                'number': node.get('number'),
                'node_type': node.get('node_type'),
                'marks': node.get('marks'),
                'matches': matches,
            })
            children = list(node.get('children') or [])
            if children:
                walk(children)

    walk(blueprint)

    return {
        'pool_entries': pool_info['pool_list'],
        'pool_size': len(pool_info['pool_list']),
        'module_filter': pool_info['module_filter'],
        'module_number': pool_info['module_number'],
        'coverage': coverage,
    }

def build_randomized_structure_from_pool(
    original_paper: Paper,
    target_paper: Paper,
    module_name: str | None,
    module_number: str | None,
    base_extractor: ExtractorPaper | None = None,
) -> Dict[str, object]:
    blueprint, _ = build_node_tree(original_paper)

    pool_info = collect_randomization_pool(module_name, module_number, base_extractor)
    pool_list = pool_info['pool_list']
    pool_size_total = len(pool_list)
    pool_by_number = pool_info['pool_by_number']
    pool_by_parent = pool_info['pool_by_parent']

    pool_size_total = len(pool_list)
    if not pool_list:
        raise RandomizationPoolError(
            "No captured snapshots found for alternate letters. "
            "Please capture boxes for additional papers before randomizing."
        )

    total_marks = 0
    used_pool = False
    order_counter = 1
    selected_boxes: list[dict] = []
    used_box_ids: set = set()
    seen_question_numbers: set[str] = set()
    # Track seen instruction/heading content to avoid materializing duplicates
    seen_instruction_keys: set[str] = set()

    def _instruction_key_from_box(box):
        # prefer stable box id
        try:
            bid = getattr(box, 'id', None)
            if bid is not None:
                return f"id:{int(bid)}"
        except Exception:
            pass
        # fallback to hashing the payload text
        import hashlib
        payload, text_value, _ = _box_payload(box)
        txt = (text_value or '')
        if not txt and isinstance(payload, list):
            txt = ' '.join([str(it.get('text','')) for it in payload if isinstance(it, dict)])
        return 'h:' + hashlib.sha1((txt or '').strip().encode('utf-8')).hexdigest()

    # We'll perform deletion and all node materialization inside a single transaction
    # so that failures during materialization do not leave orphan cover/instruction
    # nodes in the target paper. This prevents the snapshot from ending up with
    # only front-matter when questions fail to materialize.
    with transaction.atomic():
        target_paper.nodes.all().delete()

        # If the blueprint does not include any non-question root nodes (cover/instructions),
        # and there are also no question roots (this can happen when the original paper
        # itself was created from the pool), then delegate to the pool-only builder to
        # ensure questions are materialized correctly from the captured pool.
        has_non_question_root = any((root.get('node_type') or '').lower() != 'question' for root in blueprint)
        has_question_root = any((root.get('node_type') or '').lower() == 'question' for root in blueprint)
        # If there are no question roots in the blueprint, we cannot reconstruct
        # the question structure from the blueprint; fallback to pool-only builder.
        if not has_question_root:
            return build_randomized_from_pool_only(target_paper, module_name or '', module_number or '', base_extractor)

        if not has_non_question_root:
            # two-pass approach: first cover pages, then instructions/case studies
            # collect candidate orphan boxes (no qnum and no pnum)
            orphans = []
            for box in pool_list:
                qnum = (box.question_number or '').strip()
                pnum = (box.parent_number or '').strip()
                if qnum == '0':
                    qnum = ''
                if pnum == '0':
                    pnum = ''
                if qnum or pnum:
                    continue
                tkey = _normalize_box_type(getattr(box, 'qtype', ''))
                if tkey in {'cover_page', 'heading', 'instruction', 'case_study'}:
                    orphans.append(box)

            # order orphans by original capture order_index then created_at if available
            def _box_sort_key(b):
                return (getattr(b, 'order_index', 0) or 0, getattr(b, 'created_at', None) or 0, getattr(b, 'id', 0) or 0)

            orphans.sort(key=_box_sort_key)

            # first: cover pages
            added_cover = 0
            for box in [b for b in orphans if _normalize_box_type(getattr(b, 'qtype', '')) == 'cover_page']:
                payload, text_value, marks_value = _box_payload(box)
                ExamNode.objects.create(
                    paper=target_paper,
                    parent=None,
                    node_type='cover_page',
                    number=None,
                    text=text_value,
                    marks=None,
                    content=_serialize_content(payload),
                    order_index=order_counter,
                )
                order_counter += 1
                added_cover += 1
                try:
                    bid = getattr(box, 'id', None)
                    selected_boxes.append({'node_number': None, 'node_type': 'cover_page', 'box_id': int(bid) if bid is not None else None})
                    if bid is not None:
                        used_box_ids.add(bid)
                except Exception:
                    pass
                if added_cover >= 20:
                    break

            # second: instruction-like blocks (headings, instructions, case_study)
            added_instr = 0
            for box in [b for b in orphans if _normalize_box_type(getattr(b, 'qtype', '')) in {'heading', 'instruction', 'case_study'}]:
                # compute stable key and skip duplicates
                try:
                    ik = _instruction_key_from_box(box)
                except Exception:
                    ik = None
                if ik and ik in seen_instruction_keys:
                    continue
                payload, text_value, marks_value = _box_payload(box)
                ExamNode.objects.create(
                    paper=target_paper,
                    parent=None,
                    node_type='instruction',
                    number=None,
                    text=text_value,
                    marks=None,
                    content=_serialize_content(payload),
                    order_index=order_counter,
                )
                order_counter += 1
                added_instr += 1
                try:
                    bid = getattr(box, 'id', None)
                    selected_boxes.append({'node_number': None, 'node_type': 'instruction', 'box_id': int(bid) if bid is not None else None})
                    if bid is not None:
                        used_box_ids.add(bid)
                except Exception:
                    pass
                if ik:
                    seen_instruction_keys.add(ik)
                if added_instr >= 20:
                    break

    def materialize(node_dict: Dict[str, object], parent: ExamNode | None, parent_number: str | None):
        nonlocal total_marks, used_pool, order_counter
        node_type = node_dict.get('node_type') or ''
        number = node_dict.get('number') or ''
        type_key = _normalize_node_type(node_dict)
        number_key = (number or '').strip()
        parent_key = (parent_number or '').strip()

        if type_key == 'question' and number_key and number_key in seen_question_numbers:
            return

        candidates = pool_by_number.get((number_key, type_key), [])
        if not candidates and parent_key:
            candidates = pool_by_parent.get((parent_key, type_key), [])

        if not candidates:
            identifier = number_key or parent_key or '(unlabelled)'
            raise RandomizationPoolError(
                f"No captured snapshot available for {type_key} '{identifier}'. "
                "Ensure boxes exist for this item in alternate letter papers."
            )

        # prefer unused candidates to avoid duplicate captured boxes appearing
        unused = [c for c in candidates if getattr(c, 'id', None) not in used_box_ids]
        if not unused:
            # If there are no unused candidates left, allow reuse for non-question
            # node types (instructions, headings, cover pages, case studies). This
            # prevents failing the randomization when the pool is small for
            # auxiliary content. Questions still require unique candidates.
            if type_key != 'question':
                unused = list(candidates)
            else:
                identifier = number_key or parent_key or '(unlabelled)'
                raise RandomizationPoolError(
                    f"Not enough unique snapshots to randomize {type_key} '{identifier}'. "
                    f"Available: {len(candidates)} unique(s); required unique candidate not found."
                )

        chosen = random.choice(unused)
        used_pool = True
        # record which captured box supplied this node for auditability
        try:
            bid = getattr(chosen, 'id', None)
            selected_boxes.append({
                'node_number': number_key or parent_key or None,
                'node_type': type_key,
                'box_id': int(bid) if bid is not None else None,
            })
            if bid is not None:
                used_box_ids.add(bid)
        except Exception:
            # non-fatal - continue without blocking randomization
            pass
        content_payload, text_value, marks_value = _box_payload(chosen)
        header_label = chosen.header_label or ''
        case_label = chosen.case_study_label or ''
        if type_key == 'heading' and header_label:
            text_value = header_label
        if type_key == 'case_study' and case_label:
            text_value = case_label

        if not isinstance(content_payload, list):
            content_payload = []

        new_node = ExamNode.objects.create(
            paper=target_paper,
            parent=parent,
            node_type=node_type,
            number=node_dict.get('number'),
            text=text_value,
            marks=marks_value,
            content=_serialize_content(content_payload),
            order_index=order_counter,
        )
        order_counter += 1

        if (node_type or '').lower() == 'question':
            try:
                total_marks += int(new_node.marks or 0)
            except (TypeError, ValueError):
                pass
            if number_key:
                seen_question_numbers.add(number_key)

        children = list(node_dict.get('children') or [])
        question_children = [c for c in children if (c.get('node_type') or '').lower() == 'question']
        other_children = [c for c in children if (c.get('node_type') or '').lower() != 'question']
        if question_children:
            random.shuffle(question_children)
        ordered_children = other_children + question_children

        for child in ordered_children:
            materialize(child, new_node, node_dict.get('number') or parent_number)

    with transaction.atomic():
        for root in blueprint:
            materialize(root, None, None)

    return {
        'total_marks': total_marks,
        'used_pool': used_pool,
        'pool_size': pool_size_total,
        'selected_boxes': selected_boxes,
    }


def build_randomized_from_pool_only(
    target_paper: Paper,
    module_name: str,
    module_number: str,
    base_extractor: ExtractorPaper | None = None,
) -> Dict[str, object]:
    """Materialize a randomized paper directly from the snapshot pool without a blueprint.

    This constructs a simple structure:
      - Optional cover/instruction blocks (if present without a parent/question)
      - Questions in natural order by question_number
      - For each question, attach one child per auxiliary type based on parent_number

    Returns dict with total_marks, used_pool=True, pool_size.
    """
    pool_info = collect_randomization_pool(module_name, module_number, base_extractor)
    pool_list = pool_info['pool_list']
    pool_by_number = pool_info['pool_by_number']
    pool_by_parent = pool_info['pool_by_parent']

    if not pool_list:
        raise RandomizationPoolError(
            "No captured snapshots in pool. Capture boxes for this module/letter first."
        )

    # All question numbers captured (may include nested numbering like 1.1, 1.1.1)
    question_numbers_set = {
        key[0]
        for key in pool_by_number.keys()
        if key[1] == 'question' and (key[0] or '').strip()
    }
    question_numbers: list[str] = sorted(question_numbers_set, key=_natural_key)

    if not question_numbers:
        raise RandomizationPoolError(
            "Pool has no question blocks. Capture question boxes first."
        )

    # Determine parent map for question numbers using the most common parent_number among candidates
    q_parent_map: dict[str, str] = {}
    for qnum in question_numbers:
        candidates = list(pool_by_number.get((qnum, 'question'), []))
        parents = [(c.parent_number or '').strip() for c in candidates if (c.parent_number or '').strip()]
        chosen_parent = ''
        if parents:
            preferred = [p for p in parents if p and (qnum.startswith(f"{p}.") or p == qnum)]
            source = preferred if preferred else parents
            counts = Counter(source)
            chosen_parent = counts.most_common(1)[0][0]
        q_parent_map[qnum] = chosen_parent

    # Optional cover/instructions: items with no parent_number and no question_number
    # We iterate pool_list since pool_by_parent only indexes when parent_number is present.
    order_counter = 1
    total_marks = 0
    selected_boxes: list[dict] = []
    used_box_ids: set = set()
    seen_questions: set[str] = set()

    # collect orphans (no qnum, no pnum), normalise '0' markers
    orphans = []
    for box in pool_list:
        qnum = (box.question_number or '').strip()
        pnum = (box.parent_number or '').strip()
        if qnum == '0':
            qnum = ''
        if pnum == '0':
            pnum = ''
        if qnum or pnum:
            continue
        tkey = _normalize_box_type(getattr(box, 'qtype', ''))
        if tkey in {'cover_page', 'heading', 'instruction', 'case_study'}:
            orphans.append(box)

    # sort orphans by capture ordering
    def _box_sort_key(b):
        return (getattr(b, 'order_index', 0) or 0, getattr(b, 'created_at', None) or 0, getattr(b, 'id', 0) or 0)

    orphans.sort(key=_box_sort_key)

    # first: cover pages
    added_cover = 0
    for box in [b for b in orphans if _normalize_box_type(getattr(b, 'qtype', '')) == 'cover_page']:
        payload, text_value, marks_value = _box_payload(box)
        ExamNode.objects.create(
            paper=target_paper,
            parent=None,
            node_type='cover_page',
            number=None,
            text=text_value,
            marks=None,
            content=_serialize_content(payload),
            order_index=order_counter,
        )
        order_counter += 1
        try:
            bid = getattr(box, 'id', None)
            selected_boxes.append({
                'node_number': None,
                'node_type': 'cover_page',
                'box_id': int(bid) if bid is not None else None,
            })
            if bid is not None:
                used_box_ids.add(bid)
        except Exception:
            pass
        added_cover += 1
        if added_cover >= 20:
            break

    # second: instruction-like blocks
    added_instr = 0
    for box in [b for b in orphans if _normalize_box_type(getattr(b, 'qtype', '')) in {'heading', 'instruction', 'case_study'}]:
        payload, text_value, marks_value = _box_payload(box)
        ExamNode.objects.create(
            paper=target_paper,
            parent=None,
            node_type='instruction',
            number=None,
            text=text_value,
            marks=None,
            content=_serialize_content(payload),
            order_index=order_counter,
        )
        order_counter += 1
        try:
            bid = getattr(box, 'id', None)
            selected_boxes.append({
                'node_number': None,
                'node_type': 'instruction',
                'box_id': int(bid) if bid is not None else None,
            })
            if bid is not None:
                used_box_ids.add(bid)
        except Exception:
            pass
        added_instr += 1
        if added_instr >= 20:
            break

    # Build parent→children adjacency for nested question numbers
    children_map: dict[str, list[str]] = {}
    for qnum in question_numbers:
        parent = q_parent_map.get(qnum) or ''
        if parent and not qnum.startswith(f"{parent}."):
            parent = ''
        if parent:
            children_map.setdefault(parent, []).append(qnum)

    # Prepare sorted order for children under each parent
    for parent, lst in list(children_map.items()):
        lst.sort(key=_natural_key)

    # Attach in a sensible reading order
    # 1) case study/context, 2) instructions/rubric, 3) images, 4) tables
    AUX_CHILD_TYPES = ['case_study', 'instruction', 'image', 'table']

    def materialize_question(qnum: str, parent_node: ExamNode | None):
        nonlocal order_counter, total_marks
        if qnum in seen_questions:
            return
        candidates = list(pool_by_number.get((qnum, 'question'), []))
        if not candidates:
            return
        unused = [c for c in candidates if getattr(c, 'id', None) not in used_box_ids]
        if not unused:
            # no unused candidates available for this question number
            raise RandomizationPoolError(
                f"Not enough unique snapshots for question '{qnum}'. "
                f"Found {len(candidates)} candidate(s), but all were already used in this paper."
            )
        chosen = random.choice(unused)
        # record which captured box supplied this question
        try:
            bid = getattr(chosen, 'id', None)
            number_value = qnum or f"AUTO-{order_counter}"
            selected_boxes.append({
                'node_number': number_value,
                'node_type': 'question',
                'box_id': int(bid) if bid is not None else None,
            })
            if bid is not None:
                used_box_ids.add(bid)
        except Exception:
            pass
        payload, text_value, marks_value = _box_payload(chosen)
        number_value = qnum or f"AUTO-{order_counter}"
        qnode = ExamNode.objects.create(
            paper=target_paper,
            parent=parent_node,
            node_type='question',
            number=number_value,
            text=text_value,
            marks=marks_value,
            content=_serialize_content(payload),
            order_index=order_counter,
        )
        order_counter += 1
        seen_questions.add(number_value)
        try:
            total_marks += int(marks_value or 0)
        except (TypeError, ValueError):
            pass

        # Attach all auxiliary children for this question (ordered by capture order)
        for aux in AUX_CHILD_TYPES:
            aux_cands = list(pool_by_parent.get((qnum, aux), []))
            if not aux_cands:
                continue
            aux_cands.sort(key=lambda b: (getattr(b, 'order_index', 0) or 0, getattr(b, 'created_at', None) or 0, getattr(b, 'id', 0)))
            # prefer unused aux candidates
            for child in aux_cands:
                cid = getattr(child, 'id', None)
                if cid is not None and cid in used_box_ids:
                    continue
                child_payload, child_text, child_marks = _box_payload(child)
                ExamNode.objects.create(
                    paper=target_paper,
                    parent=qnode,
                    node_type='instruction' if aux in {'instruction', 'case_study'} else aux,
                    number=None,
                    text=child_text,
                    marks=None,
                    content=_serialize_content(child_payload),
                    order_index=order_counter,
                )
                order_counter += 1
                try:
                    if cid is not None:
                        used_box_ids.add(cid)
                        selected_boxes.append({
                            'node_number': qnum,
                            'node_type': aux,
                            'box_id': int(cid),
                        })
                except Exception:
                    pass
                # attach only the first unused aux candidate of this type
                break

        # Recurse into nested question numbers (e.g., 1.1 under 1)
        for child_q in children_map.get(qnum, []):
            materialize_question(child_q, qnode)

    # Identify root question numbers (no parent or parent not a question number)
    roots = [q for q in question_numbers if not (q_parent_map.get(q) and q_parent_map[q] in question_numbers_set)]
    for root_q in roots:
        materialize_question(root_q, None)

    return {
        'total_marks': total_marks,
        'used_pool': True,
        'pool_size': len(pool_list),
        'selected_boxes': selected_boxes,
    }


def calculate_pool_gaps(pool_info: dict) -> list[str]:
    """Inspect pool data and report missing question numbers where sequences have gaps."""
    pool_by_number = pool_info.get('pool_by_number', {})

    question_numbers_set = {
        key[0]
        for key in pool_by_number.keys()
        if key[1] == 'question' and (key[0] or '').strip()
    }
    question_numbers: list[str] = sorted(question_numbers_set, key=_natural_key)
    if not question_numbers:
        return []

    q_parent_map: dict[str, str] = {}
    for qnum in question_numbers:
        candidates = list(pool_by_number.get((qnum, 'question'), []))
        parents = [
            (c.parent_number or '').strip()
            for c in candidates
            if (c.parent_number or '').strip()
        ]
        chosen_parent = ''
        if parents:
            preferred = [p for p in parents if p and (qnum.startswith(f"{p}.") or p == qnum)]
            source = preferred if preferred else parents
            counts = Counter(source)
            chosen_parent = counts.most_common(1)[0][0]
        q_parent_map[qnum] = chosen_parent

    groups: dict[str, list[str]] = defaultdict(list)
    for qnum in question_numbers:
        parent = q_parent_map.get(qnum, '')
        if parent and not qnum.startswith(f"{parent}."):
            parent = ''
        groups[parent].append(qnum)

    missing: set[str] = set()
    for parent, numbers in groups.items():
        if not parent:
            continue
        numbers.sort(key=_natural_key)
        indices: set[int] = set()
        for qnum in numbers:
            parts = [segment for segment in qnum.split('.') if segment]
            if not parts:
                continue
            last = parts[-1]
            if last.isdigit():
                indices.add(int(last))
            else:
                match = re.match(r'^(\d+)', last)
                if match:
                    indices.add(int(match.group(1)))

        if not indices:
            continue

        max_index = max(indices)
        for idx in range(1, max_index + 1):
            if idx not in indices:
                candidate = f"{parent + '.' if parent else ''}{idx}"
                missing.add(candidate)

    return sorted(missing, key=_natural_key)
