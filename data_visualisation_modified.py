import matplotlib.pyplot as plt

# ============================================
# Model Evaluation Data
# ============================================
total_docs = 80
accuracy = 85.0
correct = 68
incorrect = total_docs - correct

# Confusion Data
confusion_data = {
    'invoice': {'invoice': 25, 'receipt': 5},
    'receipt': {'receipt': 29},
    'contract': {'contract': 14, 'receipt': 7}
}

# Aggregate totals per true class
true_labels = ['invoice', 'receipt', 'contract']
correct_preds = [25, 29, 14]
incorrect_preds = [5, 0, 7]
true_values = [25 + 5, 29, 14 + 7]  # total true samples
predicted_correct = [25, 29, 14]

# ============================================
# Combined Dashboard
# ============================================
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
fig.suptitle('Model Evaluation Dashboard', fontsize=16, fontweight='bold')

# 1️⃣ PIE CHART – Overall Accuracy
axes[0].pie(
    [correct, incorrect],
    labels=['Correct', 'Incorrect'],
    autopct='%1.1f%%',
    startangle=90,
    colors=['#4CAF50', '#F44336']
)
axes[0].set_title('Overall Accuracy ({}%)'.format(accuracy))

# 2️⃣ BAR GRAPH – Per-Class Performance
bar_width = 0.35
x = range(len(true_labels))
axes[1].bar(x, correct_preds, width=bar_width, label='Correct', color='#4CAF50')
axes[1].bar([i + bar_width for i in x], incorrect_preds, width=bar_width, label='Incorrect', color='#F44336')
axes[1].set_xticks([i + bar_width / 2 for i in x])
axes[1].set_xticklabels(true_labels)
axes[1].set_xlabel('Document Type')
axes[1].set_ylabel('Number of Predictions')
axes[1].set_title('Per-Class Predictions')
axes[1].legend()

# 3️⃣ SCATTER PLOT – True vs Correct Predictions
axes[2].scatter(true_values, predicted_correct, color='#2196F3', s=100)
for i, label in enumerate(true_labels):
    axes[2].text(true_values[i] + 0.2, predicted_correct[i], label, fontsize=9)
axes[2].set_xlabel('True Sample Count')
axes[2].set_ylabel('Correctly Predicted Count')
axes[2].set_title('True vs Correct Predictions')
axes[2].grid(True, linestyle='--', alpha=0.6)

plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.show()
