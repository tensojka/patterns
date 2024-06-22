# input: roz-šou-stat
# remove hyphens
# espeak-ng -vzlw/cs --ipa "rozšoustat" 2>/dev/null
# calls this via bash and receives rˈosʃoʊstat
# now we need to put hyphens back in
# rˈos-ʃoʊ-stat

# can you suggest how to do this?
# I'm thinking this could be done with a heurstic that looks at each hyphen and places it such that all the average distance from the characters from the IPA that haven't changed is as close as possible to the original. And put back in each hyphen one-by-one.

import subprocess

def get_ipa(word):
    command = f"espeak-ng -vzlw/cs --ipa '{word}' 2>/dev/null"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip()


def insert_hyphens(original, ipa):
    hyphen_positions = [i for i, char in enumerate(original) if char == '-']
    original_chars = [c for c in original if c != '-']
    result = list(ipa)
    
    for hyphen_pos in hyphen_positions:
        best_score = float('-inf')
        best_position = 0
        
        # Calculate scores for each possible hyphen position
        for i in range(len(result) + 1):
            score = 0
            ipa_left = result[:i]
            ipa_right = result[i:]

            # Compare characters to the left of the hyphen
            for j, char in enumerate(original_chars[:hyphen_pos]):
                positions = [k for k, c in enumerate(ipa_left) if c == char]
                if positions:
                    closest_pos = min(positions, key=lambda x: abs(x - j))
                    distance = abs(closest_pos - j)
                    score += max(0, 1 / (2 ** distance))

            # Compare characters to the right of the hyphen
            for j, char in enumerate(original_chars[hyphen_pos:], start=hyphen_pos):
                positions = [k for k, c in enumerate(ipa_right, start=i) if c == char]
                if positions:
                    closest_pos = min(positions, key=lambda x: abs(x - j))
                    distance = abs(closest_pos - j)
                    score += max(0, 1 / (2 ** distance))
            
            if score > best_score:
                best_score = score
                best_position = i
        
        # Insert hyphen at the best position
        result.insert(best_position, '-')
        print(f"Inserted hyphen at position {best_position} with score {best_score}")
    
    return ''.join(result)

def transform_hyphens(input_word):
    original = input_word
    word_without_hyphens = original.replace('-', '')
    ipa = get_ipa(word_without_hyphens)
    result = insert_hyphens(original, ipa)
    return result

# Test the function
print("Enter hyphenated word:")
input_word = input().strip()
output = transform_hyphens(input_word)
print(f"Input: {input_word}")
print(f"Output: {output}")