from itertools import combinations
from Levenshtein import distance

def get_hyphen_points(hyphenated):
    return [i for i, char in enumerate(hyphenated) if char == '-']

def insert_hyphens(word, positions):
    result = list(word)
    for pos in sorted(positions, reverse=True):
        result.insert(pos, '-')
    return ''.join(result)

def transform(hyphenated: str, target: str):
    origin = hyphenated.replace("-", "")
    origin_hyphen_points = get_hyphen_points(hyphenated)
    num_hyphens = len(origin_hyphen_points)
    
    possible_positions = range(1, len(target))
    best_result = None
    min_distance = float('inf')

    for hyphen_positions in combinations(possible_positions, num_hyphens):
        candidate = insert_hyphens(target, hyphen_positions)
        current_distance = distance(hyphenated, candidate)
        
        if current_distance < min_distance:
            min_distance = current_distance
            best_result = candidate

    return best_result

# Test cases
test_cases = [
    ("abc-d-ef", "axbxcdxef"),
    ("ne-boj-sa", "nebojsa"),
    ("pret-hod-ny", "predhodny"),
    ("roz-šou-stat", "rˈosʃoʊstat"),
    ("ne-roz-hod-nost", "nˈeroshˌodnost")

]

for hyphenated, target in test_cases:
    result = transform(hyphenated, target)
    print(f"Input: {hyphenated} -> {target}")
    print(f"Output: {result}\n")
