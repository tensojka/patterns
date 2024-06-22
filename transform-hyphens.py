def get_hyphen_points(hyphenated):
    hyphen_points = []
    current_index = 0
    for i, char in enumerate(hyphenated):
        if char == '-':
            hyphen_points.append(current_index)
        else:
            current_index += 1
    return hyphen_points

def transform(hyphenated: str, target: str):
    origin = hyphenated.replace("-","")
    origin_hyphen_points = get_hyphen_points(hyphenated)
    target_hyphen_points = []
    for point in origin_hyphen_points:
        best_point = None
        best_score = 0
        score = 0
        for possible_point in range(0, len(target)):
            for target_i, target_char in enumerate(target):  # target_i is where we're considering to place the hyphen
                for origin_i, origin_char in enumerate(origin):
                    if target_char == origin_char:
                        score += 1/2**abs(target_i - origin_i)
                if score > max_score:
                    max_score = score
                    best_target_i 





######

import unittest

class TestGetHyphenPoints(unittest.TestCase):
    def test_get_hyphen_points(self):
        test_cases = [
            ("a-b-c", [1, 2]),
            ("ab-cd-ef", [2, 4]),
            ("no-hyphens", [2]),
            ("", []),
            ("-a-b-", [0, 1, 2]),
            ("ne-boj-sa", [2,5])
        ]
        
        for input_str, expected in test_cases:
            with self.subTest(input_str=input_str):
                self.assertEqual(get_hyphen_points(input_str), expected)

if __name__ == '__main__':
    unittest.main()