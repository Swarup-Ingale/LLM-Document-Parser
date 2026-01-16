import os
import pandas as pd
from .document_parser import DocumentParser

class TrainingPipeline:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.parser = DocumentParser()
    
    def load_labeled_data(self) -> pd.DataFrame:
        """Load labeled documents from directory structure"""
        data = {
            'text': [],
            'document_type': [],
            'file_path': []
        }
        
        # Map directory names to document types
        type_mapping = {
            'invoices': 'invoice',
            'receipts': 'receipt',
            'contracts': 'contract',
            'letters': 'letter'
        }
        
        for folder, doc_type in type_mapping.items():
            folder_path = os.path.join(self.data_dir, folder)
            if not os.path.exists(folder_path):
                continue
                
            for filename in os.listdir(folder_path):
                if filename.endswith('.pdf'):
                    file_path = os.path.join(folder_path, filename)
                    try:
                        text = self.parser.extract_text_from_pdf(file_path)
                        if text and len(text) > 50:  # Minimum text length
                            data['text'].append(text)
                            data['document_type'].append(doc_type)
                            data['file_path'].append(file_path)
                    except Exception as e:
                        print(f"Error processing {file_path}: {e}")
        
        return pd.DataFrame(data)
    
    def run_training(self, save_path: str = "models/document_classifier.joblib"):
        """Run complete training pipeline"""
        # Load labeled data
        print("Loading training data...")
        df = self.load_labeled_data()
        
        if len(df) == 0:
            print("No labeled data found. Creating synthetic data...")
            df = self.parser.create_training_data(500)
        
        print(f"Training with {len(df)} samples")
        
        # Train the model
        self.parser.train_model(df)
        
        # Save the model
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        self.parser.save_model(save_path)
        
        print(f"Model trained and saved to {save_path}")
        
        return self.parser