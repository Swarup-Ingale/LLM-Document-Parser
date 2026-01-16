#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.training_pipeline import TrainingPipeline

def main():
    # Initialize training pipeline
    pipeline = TrainingPipeline("data/training_data")
    
    # Run training
    parser = pipeline.run_training("models/document_classifier.joblib")
    
    print("Training completed successfully!")

if __name__ == "__main__":
    main()