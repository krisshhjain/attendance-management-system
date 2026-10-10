import json
import numpy as np


RESULT_FILE = "vggface2_open_set_results.json"

THRESHOLDS = [
    0.30,
    0.35,
    0.40,
    0.45,
    0.50,
    0.55,
    0.60,
    0.65,
    0.70,
    0.75,
    0.80,
]


with open(RESULT_FILE, "r") as file:
    results = json.load(file)


known_results = results["known_results"]
unknown_results = results["unknown_results"]


print("\nThreshold Sweep")
print("=" * 90)

print(
    f"{'Threshold':>10} "
    f"{'Known ID Acc':>14} "
    f"{'Known FRR':>12} "
    f"{'Unknown FAR':>14} "
    f"{'Unknown Reject':>16}"
)

print("-" * 90)


for threshold in THRESHOLDS:

    known_correct = 0
    known_rejected = 0

    for result in known_results:

        accepted = result["distance"] <= threshold

        if accepted and result["correct"]:
            known_correct += 1

        if not accepted:
            known_rejected += 1


    known_total = len(known_results)

    known_accuracy = known_correct / known_total

    known_frr = known_rejected / known_total


    unknown_false_accepts = 0

    for result in unknown_results:

        accepted = result["distance"] <= threshold

        if accepted:
            unknown_false_accepts += 1


    unknown_total = len(unknown_results)

    unknown_far = (
        unknown_false_accepts / unknown_total
    )

    unknown_rejection = (
        1 - unknown_far
    )


    print(
        f"{threshold:10.2f} "
        f"{known_accuracy:14.3f} "
        f"{known_frr:12.3f} "
        f"{unknown_far:14.3f} "
        f"{unknown_rejection:16.3f}"
    )


print("\nDetailed false-accept analysis")
print("=" * 90)


for threshold in THRESHOLDS:

    false_accepts = [
        result
        for result in unknown_results
        if result["distance"] <= threshold
    ]

    print(
        f"\nThreshold {threshold:.2f}: "
        f"{len(false_accepts)} / "
        f"{len(unknown_results)} unknowns accepted"
    )

    for result in false_accepts:
        print(
            f"  {result['identity']} -> "
            f"{result['predicted']} "
            f"distance={result['distance']:.4f}"
        )