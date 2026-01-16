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

# ============================================
# PIE CHART – Overall accuracy
# ============================================
plt.figure(figsize=(5, 5))
plt.pie(
    [correct, incorrect],
    labels=['Correct', 'Incorrect'],
    autopct='%1.1f%%',
    startangle=90,
    colors=['#4CAF50', '#F44336']
)
plt.title('Overall Model Accuracy ({}%)'.format(accuracy))
plt.show()

# ============================================
# BAR GRAPH – Per-class performance
# ============================================
plt.figure(figsize=(7, 5))
bar_width = 0.35
x = range(len(true_labels))

plt.bar(x, correct_preds, width=bar_width, label='Correct', color='#4CAF50')
plt.bar([i + bar_width for i in x], incorrect_preds, width=bar_width, label='Incorrect', color='#F44336')

plt.xticks([i + bar_width / 2 for i in x], true_labels)
plt.xlabel('Document Type')
plt.ylabel('Number of Predictions')
plt.title('Per-Class Model Predictions')
plt.legend()
plt.tight_layout()
plt.show()

# ============================================
# SCATTER PLOT – True vs Predicted counts
# ============================================
true_values = [25 + 5, 29, 14 + 7]  # total true samples
predicted_correct = [25, 29, 14]

plt.figure(figsize=(6, 5))
plt.scatter(true_values, predicted_correct, color='#2196F3', s=100)

for i, label in enumerate(true_labels):
    plt.text(true_values[i] + 0.2, predicted_correct[i], label, fontsize=10)

plt.xlabel('True Sample Count')
plt.ylabel('Correctly Predicted Count')
plt.title('True vs Correct Predictions per Class')
plt.grid(True, linestyle='--', alpha=0.6)
plt.show()
