import matplotlib.pyplot as plt
import seaborn as sns
import pickle
import numpy as np
import sys

def plot_optimizer_behavior():
    """Load saved data and create visualization"""
    if len(sys.argv) != 2:
        print("Usage: python script.py <pkl_filename>")
        sys.exit(1)
    pkl_filename = sys.argv[1]
    with open(pkl_filename, 'rb') as f:
        data = pickle.load(f)
    
    plt.figure(figsize=(12, 6))
    
    # Plot uncertainty band
    plt.fill_between(data['iterations'], 
                    np.array(data['predictions']) - 2*np.array(data['uncertainties']),
                    np.array(data['predictions']) + 2*np.array(data['uncertainties']),
                    alpha=0.15, color='blue', label='Uncertainty Band (±σ)')
    
    # Plot actual scores and predictions
    plt.plot(data['iterations'], data['actual_scores'], 'ro', label='Actual Scores', markersize=5)
    plt.plot(data['iterations'], data['predictions'], 'b-', label='Predicted Scores', linewidth=1)
    
    plt.xlabel('Iteration', fontsize=12)
    plt.ylabel('Score', fontsize=12)
    plt.title('Bayesian Optimization Progress\nShowing scores of predicted best candidate from each batch', fontsize=14)
    plt.legend(fontsize=10)
    plt.grid(True, alpha=0.3)
    plt.gca().xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    
    plt.ylim(0, 1)
    plt.xlim(0, 50)
    
    plt.savefig(f'{pkl_filename}.png', dpi=300, bbox_inches='tight')
    plt.close()

if __name__ == "__main__":
    plot_optimizer_behavior()