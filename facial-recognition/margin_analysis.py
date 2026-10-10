import json


RESULT_FILE = "vggface2_open_set_results.json"


with open(RESULT_FILE, "r") as file:
    results = json.load(file)


known_results = results["known_results"]
unknown_results = results["unknown_results"]


print("\nImportant limitation")
print("====================")
print(
    "The current JSON stores only the best match distance, "
    "not the second-best distance."
)

print(
    "\nWe therefore need to rerun the matching calculation "
    "from the cached embeddings."
)