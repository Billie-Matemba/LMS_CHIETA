import json
import random
from pathlib import Path
from django.utils.timezone import now
from core.models import Paper
from utils_pro import populate_examnodes_from_structure_json


def randomize_paper_via_structure_json_debug(paper_id):
    original = Paper.objects.get(id=paper_id)
    print(f"📄 Randomizing Paper ID: {original.id} | Name: {original.name} | Qualification: {original.qualification}")

    pool = Paper.objects.filter(
        qualification=original.qualification,
        structure_json__isnull=False
    ).exclude(id=original.id)

    if not pool.exists():
        print("❌ No other papers found to randomize from. Aborting.")
        return original.structure_json

    prefix_map = {}
    for paper in pool:
        for block in paper.structure_json or []:
            prefix = block.get("number")
            if not prefix:
                print(f"⚠️ Skipping block with missing number in paper {paper.id}")
                continue
            prefix_map.setdefault(prefix, []).append(block)

    randomized = []
    total_marks = 0

    for block in original.structure_json or []:
        prefix = block.get("number")
        if not prefix:
            print("⚠️ Skipping original block with missing number.")
            continue
        candidates = prefix_map.get(prefix)
        if candidates:
            chosen = random.choice(candidates)
            print(f"✅ Replaced block {prefix} from a different paper.")
            randomized.append(chosen)
            try:
                total_marks += int(chosen.get("marks", 0))
            except ValueError:
                pass
        else:
            print(f"⚠️ No match found for block {prefix}, keeping original.")
            randomized.append(block)
            try:
                total_marks += int(block.get("marks", 0))
            except ValueError:
                pass

    new_paper = Paper.objects.create(
        name=f"{original.name} [Randomized {now().strftime('%Y%m%d%H%M%S')}]",
        qualification=original.qualification,
        structure_json=randomized,
        total_marks=total_marks,
        is_randomized=True
    )
    populate_examnodes_from_structure_json(new_paper)

    print(f"🎉 New randomized paper created: ID {new_paper.id} | Name: {new_paper.name} | Total Marks: {total_marks}")

    output_path = Path(f"new_paper_{new_paper.id}.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(randomized, f, indent=2)
    print(f"📝 Randomized structure saved to: {output_path.resolve()}")

    return new_paper 
