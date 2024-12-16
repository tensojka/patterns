import pickle
import os
from typing import List, Tuple
import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel

from multiprocessing import Pool

np.random.seed(42)

def evaluate_params(args):
    """Helper function for parallel evaluation"""
    input_files, weights, params_ipa, params_single, threshold, language, workdir_i = args
    good, bad, missed = sample(input_files, weights, params_ipa, params_single, threshold, language, workdir_i)
    return good, bad, missed


class PatgenSampler:
    def __init__(self):

        kernel = Matern(nu=2.5, length_scale=[1.0] * 13, length_scale_bounds=(1e-5, 1e10)) + \
                WhiteKernel(noise_level=0.1, noise_level_bounds=(1e-4, 1))
        
        self.gp = GaussianProcessRegressor(
            kernel=kernel,
            normalize_y=True,
            random_state=42,
            #alpha=0.1,
            n_restarts_optimizer=2
        )
        self.X = []
        self.y = []

    def save_state(self, filename: str):
        """Save model and training data"""
        state = {
            'gp': self.gp,
            'X': self.X,
            'y': self.y
        }
        with open(filename, 'wb') as f:
            pickle.dump(state, f)
            
    @classmethod
    def load_state(cls, filename: str):
        """Create a new sampler with loaded state"""
        sampler = cls()
        if os.path.exists(filename):
            with open(filename, 'rb') as f:
                state = pickle.load(f)
                sampler.gp = state['gp']
                sampler.X = state['X']
                sampler.y = state['y']
            print(f"Loaded {len(sampler.X)} observations from {filename}")
        return sampler

    def _encode_params(self, weights: Tuple[int, ...], params_ipa: Tuple[int, ...], 
                      params_single: Tuple[int, ...], threshold: int) -> List[float]:
        """Convert parameters to feature vector"""
        return list(weights) + list(params_ipa) + list(params_single) + [threshold]
    
        
    def _predict(self, weights: Tuple[int, ...], params_ipa: Tuple[int, ...], 
                params_single: Tuple[int, ...], threshold: int) -> Tuple[float, float]:
        """Get prediction and uncertainty for a parameter set"""
        if len(self.X) < 5:
            return 0.5, 1.0
            
        x = self._encode_params(weights, params_ipa, params_single, threshold)
        x_arr = np.array([x])
        pred, std = self.gp.predict(x_arr, return_std=True)
        return float(pred[0]), float(std[0])

    def update(self, weights: Tuple[int, ...], params_ipa: Tuple[int, ...], 
               params_single: Tuple[int, ...], threshold: int, score: float):
        """Update model with new observation"""
        x = self._encode_params(weights, params_ipa, params_single, threshold)
        self.X.append(x)
        self.y.append(score)
        
        if len(self.X) >= 5:
            X_array = np.vstack(self.X)
            y_array = np.array(self.y)
            self.gp.fit(X_array, y_array)

    def _random_params(self) -> Tuple[Tuple[int, ...], Tuple[int, ...], Tuple[int, ...], int]:
        """Generate random parameter sets"""
        weights = tuple(np.random.randint(1, 9, size=4))
        params_ipa = tuple(np.random.randint(1, 9, size=4))
        params_single = tuple(np.random.randint(1, 9, size=4))
        threshold = np.random.randint(1,9)
        return weights, params_ipa, params_single, threshold

    def _param_distance(self, params1: Tuple[Tuple[int, ...], ...], 
                       params2: Tuple[Tuple[int, ...], ...]) -> float:
        """Calculate normalized distance between parameter sets"""
        w1, i1, s1, t1 = params1
        w2, i2, s2, t2 = params2
        
        # Weight differences (max diff is 7)
        w_dist = sum(abs(a - b) for a, b in zip(w1, w2)) / (7 * 4)
        
        # Parameter differences (max diff is 5)
        i_dist = sum(abs(a - b) for a, b in zip(i1, i2)) / (5 * 4)
        s_dist = sum(abs(a - b) for a, b in zip(s1, s2)) / (5 * 4)

        t_dist = abs(t1 - t2) / 8
        
        return (w_dist + i_dist + s_dist + t_dist) / 3

    def calculate_score(self, good: int, bad: int, missed: int) -> float:
        """
        Score based on:
        - bad count is the most important (exponentially worse as it increases)
        - good count matters
        - missed count matters least
        """
        total = good + bad + missed
        
        # Exponentially penalize bad hyphenations
        bad_ratio = bad / total
        bad_penalty = np.exp(bad_ratio * 5) - 1  # exponential penalty
        
        # Reward good hyphenations
        good_ratio = good / total
        
        # Combine (normalizing to 0-1)
        score = good_ratio - bad_penalty
        return max(0.0, min(1.0, (score + 1) / 2))
    
    def suggest_batch(self, n_suggestions: int = 5, n_candidates: int = 10000) -> List[Tuple[Tuple[int, ...], Tuple[int, ...], Tuple[int, ...]]]:
        """Suggest a batch of diverse, promising parameter sets with predictions"""
        if len(self.X) < 5:
            suggestions = [self._random_params() for _ in range(n_suggestions)]
            return [(params, *self._predict(*params)) for params in suggestions]
            
        # Generate candidates
        candidates = [self._random_params() for _ in range(n_candidates)]
        X_candidates = np.array([self._encode_params(*c) for c in candidates])
        
        # Get predictions and uncertainties
        mean, std = self.gp.predict(X_candidates, return_std=True)
        scores = mean + 2.0 * std
        
        # Select diverse set from top quartile
        top_quartile = np.percentile(scores, 75)
        good_indices = np.where(scores >= top_quartile)[0]
        
        selected = []
        selected_indices = []
        
        # Always include the absolute best
        best_idx = np.argmax(scores)
        selected.append(candidates[best_idx])
        selected_indices.append(best_idx)
        
        while len(selected) < n_suggestions and len(good_indices) > 0:
            max_min_dist = -1
            best_idx = -1
            
            for idx in good_indices:
                if idx in selected_indices:
                    continue
                    
                dists = [self._param_distance(candidates[idx], sel) 
                        for sel in selected]
                min_dist = min(dists)
                
                if min_dist > max_min_dist:
                    max_min_dist = min_dist
                    best_idx = idx
            
            if best_idx != -1:
                selected.append(candidates[best_idx])
                selected_indices.append(best_idx)
                good_indices = good_indices[good_indices != best_idx]
            else:
                break
                
        # Add predictions for selected candidates
        return [(params, *self._predict(*params)) for params in selected]
        
    def exploit_best_candidates(self, n_suggestions=10, n_candidates=20000):
        """Generate many candidates and return the ones with highest predicted scores, no exploration"""
        if len(self.X) < 5:
            return self.suggest_batch(n_suggestions)
            
        # Generate lots of candidates
        candidates = [self._random_params() for _ in range(n_candidates)]
        X_candidates = np.array([self._encode_params(*c) for c in candidates])
        
        # Get just predictions, no uncertainty consideration
        mean = self.gp.predict(X_candidates)
        
        # Get top predicted performers
        top_indices = np.argsort(mean)[-n_suggestions:][::-1]
        
        return [(candidates[i], float(mean[i]), 0.0) for i in top_indices]  # Convert to float for safety

def print_param_set(weights: Tuple[int, ...], params_ipa: Tuple[int, ...], 
                   params_single: Tuple[int, ...], threshold: int = 5, predicted_score: float = None,
                   uncertainty: float = None, actual_score: float = None):
    """Pretty print a parameter set with predictions"""
    print("\nWeights:        ", " ".join(map(str, weights)))
    print("IPA Params:     ", " ".join(map(str, params_ipa)))
    print("Single Params:  ", " ".join(map(str, params_single)))
    print(f"Threshold:       {threshold}")
    if predicted_score is not None and uncertainty is not None:
        print(f"Predicted score: {predicted_score:.3f} ± {uncertainty:.3f}")
    if actual_score is not None:
        print(f"Actual score:    {actual_score:.3f}")
        if predicted_score is not None:
            error = abs(predicted_score - actual_score)
            print(f"Prediction error: {error:.3f}")


from evaluate_data_mix import sample

def collect_optimizer_data():
    """Run optimization and save data for later plotting"""
    sampler = PatgenSampler()
    LANGUAGE = "uk"
    input_files = ["work/pl.ipa.wlh", "work/sk.ipa.wlh", "work/uk.ipa.wlh", "work/ru.ipa.wlh"]
    
    data = {
        'iterations': [],
        'predictions': [],
        'uncertainties': [],
        'actual_scores': []
    }

    for iteration in range(50):
        print(f"\nIteration {iteration}")
        
        # Get exploration suggestions and one exploitation suggestion
        explore_sets = sampler.suggest_batch(n_suggestions=5, n_candidates=5000)
        exploit_sets = sampler.exploit_best_candidates(n_suggestions=1, n_candidates=20000)
        
        # Get uncertainty for the exploited candidate
        params = exploit_sets[0][0]  # (weights, params_ipa, params_single, threshold)
        pred_score, uncertainty = sampler._predict(*params)
        
        # Combine all sets for parallel evaluation
        all_sets = explore_sets + [(params, pred_score, uncertainty)]
        
        # Prepare parallel evaluation args
        eval_args = [
            (input_files, weights, params_ipa, params_single, threshold, LANGUAGE, i)
            for i, ((weights, params_ipa, params_single, threshold), _, _) in enumerate(all_sets)
        ]
        
        # Evaluate all suggestions in parallel
        with Pool() as pool:
            results = pool.map(evaluate_params, eval_args)
        
        # Update model with exploration results
        for (params, _, _), (good, bad, missed) in zip(explore_sets, results[:5]):
            weights, params_ipa, params_single, threshold = params
            actual_score = sampler.calculate_score(good, bad, missed)
            sampler.update(weights, params_ipa, params_single, threshold, actual_score)
        
        # Process and store exploitation result
        (good, bad, missed) = results[5]
        actual_score = sampler.calculate_score(good, bad, missed)
        sampler.update(*params, actual_score)
        
        # Store data for plotting
        data['iterations'].append(iteration)
        data['predictions'].append(pred_score)
        data['uncertainties'].append(uncertainty)
        data['actual_scores'].append(actual_score)
        
        print(f"Exploitation - predicted: {pred_score:.3f} ± {uncertainty:.3f}, actual: {actual_score:.3f}")

        with open('optimizer_behavior.pkl', 'wb') as f:
            pickle.dump(data, f)

    return sampler


def main_parallel():
    RANDOM_SAMPLE_LEN = 10
    EXPLORATION_ROUNDS = 10
    SAMPLES_PER_EXPLORATION_ROUND = 10

    sampler = PatgenSampler()
    lang = os.getenv("TARGET_LANGUAGE")
    LANGUAGE = lang if lang is not None else "pl"
    RANDOM_SAMPLE = True
    EXPLORATION = True
    EXPLOITATION = True

    data = {
        'iterations': [],
        'predictions': [],
        'uncertainties': [],
        'actual_scores': []
    }

    if LANGUAGE == "pl":
        input_files = ["work/cs.ipa.wlh", "work/pl.ipa.wlh", "work/sk.ipa.wlh", "work/ru.ipa.wlh"]
    elif LANGUAGE == "uk":
        input_files = ["work/pl.ipa.wlh", "work/sk.ipa.wlh", "work/uk.ipa.wlh", "work/ru.ipa.wlh"]
    else:
        raise ValueError(f"language {LANGUAGE} unsupported for optimization")

    sampler = PatgenSampler.load_state(f"work/model{LANGUAGE}.pkl")

    if RANDOM_SAMPLE:
        print(f"Randomly sampling {RANDOM_SAMPLE_LEN} parameter sets")
        initial_sets = sampler.suggest_batch(n_suggestions=RANDOM_SAMPLE_LEN)
        
        # Prepare parallel evaluation args
        eval_args = [
            (input_files, weights, params_ipa, params_single, threshold, LANGUAGE, i)
            for i, ((weights, params_ipa, params_single, threshold), _, _) in enumerate(initial_sets)
        ]
        
        # Run evaluations in parallel
        with Pool() as pool:
            results = pool.map(evaluate_params, eval_args)
        
        # Process results and update model
        for (params, pred_score, uncertainty), (good, bad, missed) in zip(initial_sets, results):
            weights, params_ipa, params_single, threshold = params
            actual_score = sampler.calculate_score(good, bad, missed)
            print(f"Evaluation: good={good}, bad={bad}, missed={missed}")
            print(f"Actual score: {actual_score:.3f}")

            sampler.update(weights, params_ipa, params_single, threshold, actual_score)


    if EXPLORATION:
        # Get more suggestions informed by previous scores
        n_processes = int(os.getenv('RAYON_NUM_THREADS', os.cpu_count()))
        print(f"Running with {n_processes} processes")
        with Pool(processes=n_processes) as pool:
            for round in range(EXPLORATION_ROUNDS):
                print("="*70)
                print(f"Round {round}")

                next_sets = sampler.suggest_batch(n_suggestions=SAMPLES_PER_EXPLORATION_ROUND)
                exploit_sets = sampler.exploit_best_candidates(n_suggestions=1)
                
                # Get uncertainty for the exploited candidate
                exploit_params = exploit_sets[0][0]
                pred_score, uncertainty = sampler._predict(*exploit_params)
                
                # Combine all sets for parallel evaluation
                all_sets = next_sets + [(exploit_params, pred_score, uncertainty)]
                
                # Prepare parallel evaluation args
                eval_args = [
                    (input_files, weights, params_ipa, params_single, threshold, LANGUAGE, i) 
                    for i, ((weights, params_ipa, params_single, threshold), _, _) in enumerate(all_sets)
                ]
                
                # Run evaluations in parallel
                results = pool.map(evaluate_params, eval_args)
                
                # Process results and update model
                for (params, pred_score, uncertainty), (good, bad, missed) in zip(next_sets, results[:SAMPLES_PER_EXPLORATION_ROUND]):
                    weights, params_ipa, params_single, threshold = params
                    print_param_set(weights, params_ipa, params_single, threshold, pred_score, uncertainty)
                    actual_score = sampler.calculate_score(good, bad, missed)
                    print(f"Evaluation: good={good}, bad={bad}, missed={missed}")
                    print(f"Actual score: {actual_score:.3f}")
                    sampler.update(weights, params_ipa, params_single, threshold, actual_score)
                
                # Process and store exploitation result
                (good, bad, missed) = results[SAMPLES_PER_EXPLORATION_ROUND]
                actual_score = sampler.calculate_score(good, bad, missed)
                sampler.update(*exploit_params, actual_score)

                # Store data for plotting
                data['iterations'].append(round)
                data['predictions'].append(pred_score)
                data['uncertainties'].append(uncertainty)
                data['actual_scores'].append(actual_score)
                
                print(f"\nExploitation - predicted: {pred_score:.3f} ± {uncertainty:.3f}, actual: {actual_score:.3f}")
                
                # Save data after each round
                with open(f'optimizer_behavior_{LANGUAGE}.pkl', 'wb') as f:
                    pickle.dump(data, f)


    if EXPLOITATION:
        print("="*70)
        print("!"*70)
        print("="*70)
        print("\nFinal exploitation phase - best predicted configurations:")
        best_candidates = sampler.exploit_best_candidates(n_suggestions=5)
        for params, pred_score, _ in best_candidates:
            weights, params_ipa, params_single, threshold = params
            print_param_set(weights, params_ipa, params_single, threshold, pred_score)
            
            # Evaluate
            good, bad, missed = sample(input_files, weights, params_ipa, params_single, threshold, LANGUAGE)
            actual_score = sampler.calculate_score(good, bad, missed)
            print(f"Actual score: {actual_score:.3f}")
            print(f"Evaluation: good={good}, bad={bad}, missed={missed}")
            sampler.update(weights, params_ipa, params_single, threshold, actual_score)


    sampler.save_state(f"work/model{LANGUAGE}.pkl")

def main_reproducible():
    RANDOM_SAMPLE_LEN = 10
    EXPLORATION_ROUNDS = 50
    SAMPLES_PER_EXPLORATION_ROUND = 10

    sampler = PatgenSampler()
    lang = os.getenv("TARGET_LANGUAGE")
    LANGUAGE = lang if lang is not None else "pl"
    RANDOM_SAMPLE = True
    EXPLORATION = True
    EXPLOITATION = True

    data = {
        'iterations': [],
        'predictions': [],
        'uncertainties': [],
        'actual_scores': []
    }

    # Set up input files based on language
    if LANGUAGE == "pl":
        input_files = ["work/cs.ipa.wlh", "work/pl.ipa.wlh", "work/sk.ipa.wlh", "work/ru.ipa.wlh"]
    elif LANGUAGE == "uk":
        input_files = ["work/pl.ipa.wlh", "work/sk.ipa.wlh", "work/uk.ipa.wlh", "work/ru.ipa.wlh"]
    else:
        raise ValueError(f"language {LANGUAGE} unsupported for optimization")

    sampler = PatgenSampler.load_state(f"work/model{LANGUAGE}.pkl")

    if RANDOM_SAMPLE:
        print(f"Randomly sampling {RANDOM_SAMPLE_LEN} parameter sets")
        initial_sets = sampler.suggest_batch(n_suggestions=RANDOM_SAMPLE_LEN)
        
        # Sequential evaluation
        for i, (params, pred_score, uncertainty) in enumerate(initial_sets):
            weights, params_ipa, params_single, threshold = params
            good, bad, missed = sample(input_files, weights, params_ipa, params_single, threshold, LANGUAGE, i)
            actual_score = sampler.calculate_score(good, bad, missed)
            print(f"Evaluation: good={good}, bad={bad}, missed={missed}")
            print(f"Actual score: {actual_score:.3f}")
            sampler.update(weights, params_ipa, params_single, threshold, actual_score)

    if EXPLORATION:
        for round in range(EXPLORATION_ROUNDS):
            print("="*70)
            print(f"Round {round}")

            # Handle exploration sets
            next_sets = sampler.suggest_batch(n_suggestions=SAMPLES_PER_EXPLORATION_ROUND)
            for params, pred_score, uncertainty in next_sets:
                weights, params_ipa, params_single, threshold = params
                print_param_set(weights, params_ipa, params_single, threshold, pred_score, uncertainty)
                good, bad, missed = sample(input_files, weights, params_ipa, params_single, threshold, LANGUAGE)
                actual_score = sampler.calculate_score(good, bad, missed)
                print(f"Evaluation: good={good}, bad={bad}, missed={missed}")
                print(f"Actual score: {actual_score:.3f}")
                sampler.update(weights, params_ipa, params_single, threshold, actual_score)

            # Handle single exploitation set
            exploit_sets = sampler.exploit_best_candidates(n_suggestions=1)
            params, pred_score, _ = exploit_sets[0]
            weights, params_ipa, params_single, threshold = params
            _, uncertainty = sampler._predict(*params)
            
            good, bad, missed = sample(input_files, weights, params_ipa, params_single, threshold, LANGUAGE)
            actual_score = sampler.calculate_score(good, bad, missed)
            sampler.update(weights, params_ipa, params_single, threshold, actual_score)
            
            # Store data for plotting
            data['iterations'].append(round)
            data['predictions'].append(pred_score)
            data['uncertainties'].append(uncertainty)
            data['actual_scores'].append(actual_score)
            
            print(f"\nExploitation - predicted: {pred_score:.3f} ± {uncertainty:.3f}, actual: {actual_score:.3f}")
            
            # Save data after each round
            with open(f'optimizer_behavior_{LANGUAGE}.pkl', 'wb') as f:
                pickle.dump(data, f)

    if EXPLOITATION:
        print("="*70)
        print("!"*70)
        print("="*70)
        print("\nFinal exploitation phase - best predicted configurations:")
        best_candidates = sampler.exploit_best_candidates(n_suggestions=5)
        for params, pred_score, _ in best_candidates:
            weights, params_ipa, params_single, threshold = params
            print_param_set(weights, params_ipa, params_single, threshold, pred_score)
            
            good, bad, missed = sample(input_files, weights, params_ipa, params_single, threshold, LANGUAGE)
            actual_score = sampler.calculate_score(good, bad, missed)
            print(f"Actual score: {actual_score:.3f}")
            print(f"Evaluation: good={good}, bad={bad}, missed={missed}")
            sampler.update(weights, params_ipa, params_single, threshold, actual_score)

    sampler.save_state(f"work/model{LANGUAGE}.pkl")

if __name__ == '__main__':
    # To collect optimizer data:
    #collect_optimizer_data()
    main_reproducible()
    #print(sample(["work/pl.ipa.wlh", "work/sk.ipa.wlh", "work/uk.ipa.wlh", "work/ru.ipa.wlh"], (1,1,1,1), (3,3,3,3), (4,4,4,4), 5, 'uk', 42))