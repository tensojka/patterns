import pickle
import os
from typing import List, Tuple
import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern

def export_optimization_data(sampler):
    """Export optimization data to JSON format"""
    import json
    from datetime import datetime
    
    data = []
    # Reconstruct evaluations from stored data
    for i in range(len(sampler.X)):
        x = sampler.X[i]
        # Convert back to original parameter format
        weights = tuple(int(x[j]) for j in range(4))
        params_ipa = tuple(int(x[j]) for j in range(4, 8))
        params_single = tuple(int(x[j]) for j in range(8, 12))
        
        # Get prediction and uncertainty for this point
        pred, std = sampler.gp.predict([x], return_std=True)
        
        entry = {
            "iteration": i,
            "weights": list(weights),
            "params_ipa": list(params_ipa),
            "params_single": list(params_single),
            "predicted_score": float(pred[0]),
            "uncertainty": float(std[0]),
            "actual_score": float(sampler.y[i])
        }
        data.append(entry)
    
    # Add final exploitation phase if it exists
    # ... you'd need to store these separately in the sampler
    
    output = {
        "timestamp": datetime.now().isoformat(),
        "total_iterations": len(data),
        "best_score": max(entry["actual_score"] for entry in data),
        "data": data
    }
    
    filename = f"optimization_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(output, f, indent=2)
        
    return filename

class PatgenSampler:
    def __init__(self):
        self.gp = GaussianProcessRegressor(
            kernel=Matern(nu=2.5),
            normalize_y=True,
            random_state=42
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
        return sampler

    def _encode_params(self, weights: Tuple[int, ...], params_ipa: Tuple[int, ...], 
                      params_single: Tuple[int, ...]) -> List[float]:
        """Convert parameters to feature vector"""
        return list(weights) + list(params_ipa) + list(params_single)
    
        
    def _predict(self, weights: Tuple[int, ...], params_ipa: Tuple[int, ...], 
                params_single: Tuple[int, ...]) -> Tuple[float, float]:
        """Get prediction and uncertainty for a parameter set"""
        if len(self.X) < 5:
            return 0.5, 1.0
            
        x = self._encode_params(weights, params_ipa, params_single)
        x_arr = np.array([x])
        pred, std = self.gp.predict(x_arr, return_std=True)
        return float(pred[0]), float(std[0])

    def update(self, weights: Tuple[int, ...], params_ipa: Tuple[int, ...], 
               params_single: Tuple[int, ...], score: float):
        """Update model with new observation"""
        x = self._encode_params(weights, params_ipa, params_single)
        self.X.append(x)
        self.y.append(score)
        
        if len(self.X) >= 5:
            X_array = np.vstack(self.X)
            y_array = np.array(self.y)
            self.gp.fit(X_array, y_array)

    def _random_params(self) -> Tuple[Tuple[int, ...], Tuple[int, ...], Tuple[int, ...]]:
        """Generate random parameter sets"""
        weights = tuple(np.random.choice([0, 1, 3, 5, 7], size=4))
        params_ipa = tuple(np.random.randint(1, 7, size=4))
        params_single = tuple(np.random.randint(1, 7, size=4))
        return weights, params_ipa, params_single

    def _param_distance(self, params1: Tuple[Tuple[int, ...], ...], 
                       params2: Tuple[Tuple[int, ...], ...]) -> float:
        """Calculate normalized distance between parameter sets"""
        w1, i1, s1 = params1
        w2, i2, s2 = params2
        
        # Weight differences (max diff is 7)
        w_dist = sum(abs(a - b) for a, b in zip(w1, w2)) / (7 * 4)
        
        # Parameter differences (max diff is 5)
        i_dist = sum(abs(a - b) for a, b in zip(i1, i2)) / (5 * 4)
        s_dist = sum(abs(a - b) for a, b in zip(s1, s2)) / (5 * 4)
        
        return (w_dist + i_dist + s_dist) / 3

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
    
    def suggest_batch(self, n_suggestions: int = 5, n_candidates: int = 5000) -> List[Tuple[Tuple[int, ...], Tuple[int, ...], Tuple[int, ...]]]:
        """Suggest a batch of diverse, promising parameter sets with predictions"""
        if len(self.X) < 5:
            suggestions = [self._random_params() for _ in range(n_suggestions)]
            return [(params, *self._predict(*params)) for params in suggestions]
            
        # Generate candidates
        candidates = [self._random_params() for _ in range(n_candidates)]
        X_candidates = np.array([self._encode_params(*c) for c in candidates])
        
        # Get predictions and uncertainties
        mean, std = self.gp.predict(X_candidates, return_std=True)
        scores = mean + std
        
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
        
    def exploit_best_candidates(self, n_suggestions=10, n_candidates=10000):
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
        
        return [(candidates[i], mean[i], 0.0) for i in top_indices]

def print_param_set(weights: Tuple[int, ...], params_ipa: Tuple[int, ...], 
                   params_single: Tuple[int, ...], predicted_score: float = None,
                   uncertainty: float = None, actual_score: float = None):
    """Pretty print a parameter set with predictions"""
    print("\nWeights:        ", " ".join(map(str, weights)))
    print("IPA Params:     ", " ".join(map(str, params_ipa)))
    print("Single Params:  ", " ".join(map(str, params_single)))
    if predicted_score is not None:
        print(f"Predicted score: {predicted_score:.3f} ± {uncertainty:.3f}")
    if actual_score is not None:
        print(f"Actual score:    {actual_score:.3f}")
        if predicted_score is not None:
            error = abs(predicted_score - actual_score)
            print(f"Prediction error: {error:.3f}")


from evaluate_data_mix import sample

RANDOM_SAMPLE_LEN = 5
EXPLORATION_ROUNDS = 20
EXPLOITATION_ROUNDS = 5

sampler = PatgenSampler()
LANGUAGE = "pl"
RANDOM_SAMPLE = True
EXPLORATION = True
EXPLOITATION = True

if LANGUAGE == "pl":
    input_files = ["work/cs.ipa.wlh", "work/pl.ipa.wlh", "work/sk.ipa.wlh", "work/ru.ipa.wlh"]
elif LANGUAGE == "uk":
    input_files = ["work/pl.ipa.wlh", "work/sk.ipa.wlh", "work/uk.ipa.wlh", "work/ru.ipa.wlh"]
else:
    raise ValueError(f"language {LANGUAGE} unsupported for optimization")

sampler.load_state("work/model.pkl")

if RANDOM_SAMPLE:
    print(f"Randomly sampling {RANDOM_SAMPLE_LEN} parameter sets")
    initial_sets = sampler.suggest_batch(n_suggestions=RANDOM_SAMPLE_LEN)
    for params, pred_score, uncertainty in initial_sets:
        weights, params_ipa, params_single = params
        print_param_set(weights, params_ipa, params_single, pred_score, uncertainty)

        # Run evaluation
        good, bad, missed = sample(input_files, weights, params_ipa, params_single, LANGUAGE)
        actual_score = sampler.calculate_score(good, bad, missed)
        print(f"Evaluation: good={good}, bad={bad}, missed={missed}")
        print(f"Actual score: {actual_score:.3f}")
        
        # Update model
        sampler.update(weights, params_ipa, params_single, actual_score)

if EXPLORATION:
    # Get more suggestions informed by previous scores
    for round in range(EXPLORATION_ROUNDS):
        print("="*70)
        print(f"Round {round}")
        print("\nNext batch of suggestions based on results:")
        next_sets = sampler.suggest_batch(n_suggestions=4)
        for params, pred_score, uncertainty in next_sets:
            weights, params_ipa, params_single = params
            print_param_set(weights, params_ipa, params_single, pred_score, uncertainty)
            
            # Run evaluation
            good, bad, missed = sample(input_files, weights, params_ipa, params_single, LANGUAGE)
            actual_score = sampler.calculate_score(good, bad, missed)
            print(f"Evaluation: good={good}, bad={bad}, missed={missed}")
            print(f"Actual score: {actual_score:.3f}")
            
            # Update model
            sampler.update(weights, params_ipa, params_single, actual_score)

if EXPLOITATION:
    print("="*70)
    print("!"*70)
    print("="*70)
    print("\nFinal exploitation phase - best predicted configurations:")
    best_candidates = sampler.exploit_best_candidates(n_suggestions=EXPLOITATION_ROUNDS)
    for params, pred_score, _ in best_candidates:
        weights, params_ipa, params_single = params
        print("\nPredicted score:", f"{pred_score:.3f}")
        print("Weights:       ", " ".join(map(str, weights)))
        print("IPA Params:    ", " ".join(map(str, params_ipa)))
        print("Single Params: ", " ".join(map(str, params_single)))
        
        # Evaluate
        good, bad, missed = sample(input_files, weights, params_ipa, params_single, LANGUAGE)
        actual_score = sampler.calculate_score(good, bad, missed)
        print(f"Actual score: {actual_score:.3f}")
        print(f"Evaluation: good={good}, bad={bad}, missed={missed}")
        sampler.update(weights, params_ipa, params_single, actual_score)

export_optimization_data(sampler)
sampler.save_state("work/model.pkl")