import argparse
import sys
from dataclasses import dataclass
from typing import List, Tuple
import csv
import time
from tqdm import tqdm
import spacy
import ipdb
import nltk
from nltk import sent_tokenize


from data_preparation.data_loader import load_corpus_json#, get_slavonic_function_words
from data_preparation.segmentation import Segmentation
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Any, Union
import numpy as np
import spacy
from sklearn.base import BaseEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold, GridSearchCV
from sklearn.metrics import (
    f1_score, 
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
    classification_report,
    make_scorer
)

from feature_extraction.features import (
    DocumentProcessor,
    #FeaturesFunctionWords,
    #FeaturesDistortedView,
    FeaturesMendenhall,
    FeaturesSentenceLength,
    FeaturesPOST,
    FeatureSetReductor,
    #FeaturesDEP,
    #FeaturesPunctuation,
    HstackFeatureSet,
    FeaturesCharNGram,
    #FeaturesVerbalEndings,
    #FeaturesSyllabicQuantities
)


@dataclass
class ModelConfig:
    """Configuration for the model training and evaluation"""
    n_jobs: int = 32
    segment_min_token_size: int = 400
    random_state: int = 0
    k_ratio: float = 0.8
    oversample: bool = False
    rebalance_ratio: float = 0.5
    save_res: bool = True
    #test_genre: bool = False
    results_filename: str = 'results.csv'
    results_path: str = './results'   

    @classmethod
    def from_args(cls):
        """Create config from command line args"""
        parser = argparse.ArgumentParser()
        parser.add_argument('--results-filename', default='results.csv',
                    help='Filename for saving results')
        parser.add_argument('--results-path', 
                    default='./results',
                    help='Directory path for saving results')
        args = parser.parse_args()
            
        config = cls()
        config.results_filename = args.results_filename
        config.results_path = args.results_path
        
        return config
            
class EpochshipVerification:
    """Main class for epochship verification system"""
    
    def __init__(self, config: ModelConfig, nlp: spacy.Language):#nlp: stanza.Pipeline):
        self.config = config
        self.nlp = nlp
        self.accuracy = 0
        self.posterior_proba = 0
        
    def load_dataset(self,  
                     path: str = 'file_versions/ocs_cs_cleaned_reordered.json'
                     ) -> Tuple[List[str], List[str], List[str]]:
        
        print('Loading data...')
        documents, epochs, filenames = load_corpus_json(
            json_path=path, 
            skip_ruthenians=False,
        )
        print('Data loaded.')
        return documents, epochs, filenames
    
    def loo_split(self, i: int, X: List[str], y: List[int], doc: str, ylabel: int, 
        filenames: List[str]) -> Tuple[List[str], List[str], List[int], List[int], List[str], List[str]]:
        
        doc_name = filenames[i]
        print(f'Test document: {doc_name[:-2]}')
        
        X_test = [doc]
        y_test = [int(ylabel)]
        X_dev = list(np.delete(X, i))
        y_dev = list(np.delete(y, i))
        groups_dev = list(np.delete(filenames, i))
        
        return X_dev, X_test, y_dev, y_test, groups_dev, [doc_name]
    
    def segment_data(self, X_dev: List[str], X_test: List[str], y_dev: List[int], 
                    y_test: List[int], groups_dev: List[str], groups_test: List[str]
                    ) -> Tuple[List[str], List[str], List[int], List[int], List[str], List[str], List[str]]:
        """Segment the documents into smaller chunks"""
        
        print('Segmenting data...')
        whole_docs_len = len(y_test)

        segmentator_dev = Segmentation(
            split_policy='by_sentence',
            tokens_per_fragment=self.config.segment_min_token_size,
            #nlp=self.nlp
        )
        splitted_docs_dev = segmentator_dev.fit_transform(
            documents=X_dev,
            epochs=y_dev,
            filenames=groups_dev
        )

        segmentator_test = Segmentation(
            split_policy='by_sentence',
            tokens_per_fragment=self.config.segment_min_token_size, 
            #nlp=self.nlp
        )
        splitted_docs_test = segmentator_test.transform(
            documents=X_test,
            epochs=y_test,
            filenames=groups_test
        )
        groups_test = segmentator_test.groups

        X_dev = splitted_docs_dev[0]
        y_dev = splitted_docs_dev[1]
        groups_dev = segmentator_dev.groups

        X_test = splitted_docs_test[0][:whole_docs_len]
        y_test = splitted_docs_test[1][:whole_docs_len]
        groups_test_entire_docs = groups_test[:whole_docs_len]

        X_test_frag = splitted_docs_test[0][whole_docs_len:]
        y_test_frag = splitted_docs_test[1][whole_docs_len:]
        groups_test_frag = groups_test[whole_docs_len:]

        print('Segmentation complete.')
        
        return (X_dev, X_test, y_dev, y_test, X_test_frag, y_test_frag, 
                groups_dev, groups_test_entire_docs, groups_test_frag)
        
    def get_processed_documents(self, documents: List[str], filenames: List[str], 
                              processed: bool = False, 
                              cache_file: str = '.cache/processed_docs.pkl') -> Dict[str, spacy.tokens.Doc]:
        """Process documents using spaCy"""
        print('Processing documents...')
        
        if not processed:
            self.nlp.max_length = max(len(doc) for doc in documents)
            processor = DocumentProcessor(language_model=self.nlp, savecache=cache_file)
            processed_docs = processor.process_documents(documents, filenames)
        else:
            processor = DocumentProcessor(savecache=cache_file)
            processed_docs = processor.process_documents(documents, filenames)
            #ipdb.set_trace()
        
        return processed_docs
    
    
    def find_segment(self, segment: str, processed_document: spacy.tokens.Doc) -> spacy.tokens.Span:
        """Find a segment within a processed document"""
        #doc = self.nlp(segment)
        #start_segment = doc.sentences[0].text
        start_segment = sent_tokenize(segment)[0]
        start_idx = processed_document.text.find(start_segment)
        end_idx = start_idx + len(segment)
        #ipdb.set_trace()
        
        processed_seg = processed_document.char_span(start_idx, end_idx, alignment_mode='expand')
        if not processed_seg:
            processed_seg = processed_document.char_span(start_idx, end_idx-1, alignment_mode='expand')
        
        return processed_seg

    def get_processed_segments(self, processed_docs: Dict[str, spacy.tokens.Doc], 
                             X: List[str], groups: List[str], dataset: str = ''
                             ) -> List[Union[spacy.tokens.Doc, spacy.tokens.Span]]:
        """Extract processed segments from documents"""
        print(f'Extracting processed {dataset} segments...')
        
        none_count = 0
        processed_X = []
        
        for segment, group in tqdm(zip(X, groups), total=len(X), desc='Progress'):
            if group.endswith('_0_0'):  # entire doc
                processed_doc = processed_docs[group[:-4]]## TODO: CONTROLLARE SE L'OUTPUT QUI è QUELLO CHE CI ASPETTIAMO
                processed_X.append(processed_doc)
            else:  # segment
                group_idx = group.find('_0')
                group_key = group[:group_idx]
                ent_doc_processed = processed_docs[group_key]
                processed_segment = self.find_segment(segment, ent_doc_processed)
                
                if not processed_segment:
                    none_count += 1
  
                processed_X.append(processed_segment)
                #ipdb.set_trace()
        
        print(f'None count: {none_count}\n')
        #ipdb.set_trace()
        return processed_X

    def extract_feature_vectors(self, processed_docs_dev: List[spacy.tokens.Doc], 
                              processed_docs_test: List[spacy.tokens.Doc],
                              y_dev: List[int], y_test: List[int], 
                              groups_dev: List[str]) -> Tuple[np.ndarray, ...]:
        
        print('Extracting feature vectors...')

        #latin_function_words = get_slavonic_function_words()
        vectorizers = [
            #FeaturesFunctionWords(
                #function_words=latin_function_words, 
                #ngram_range=(1,1)
            #),
            FeaturesPOST(n=(1,3)),
            FeaturesMendenhall(upto=20),
            FeaturesSentenceLength(),
            FeaturesCharNGram(n=(1,3))
        ]
        #ipdb.set_trace()

        hstacker = HstackFeatureSet(vectorizers)
        feature_sets_dev = []
        feature_sets_test = []
        feature_sets_dev_orig = []
        feature_sets_test_orig = []
        orig_groups_dev = groups_dev.copy()

        for vectorizer in vectorizers:
            print(f'\nExtracting {vectorizer}')
            reductor = FeatureSetReductor(
                vectorizer, 
                k_ratio=self.config.k_ratio
            )
            #ipdb.set_trace()

            print('\nProcessing development set')
            features_set_dev = reductor.fit_transform(processed_docs_dev, y_dev)
            #ipdb.set_trace()

            print('\nProcessing test set')
            features_set_test = reductor.transform(processed_docs_test)
            #ipdb.set_trace()

            if self.config.oversample:
                feature_sets_dev_orig.append(features_set_dev)
                feature_sets_test_orig.append(features_set_test)
                orig_y_dev = y_dev.copy()
                #ipdb.set_trace()

                (features_set_dev, y_dev_oversampled, features_set_test, 
                 y_test_oversampled, groups_dev) = reductor.oversample_DRO(
                    Xtr=features_set_dev,
                    ytr=y_dev,
                    Xte=features_set_test,
                    yte=y_test,
                    groups=orig_groups_dev,
                    rebalance_ratio=self.config.rebalance_ratio
                )
                #ipdb.set_trace()
                feature_sets_dev.append(features_set_dev)
                feature_sets_test.append(features_set_test)
            else:
                feature_sets_dev.append(features_set_dev)
                feature_sets_test.append(features_set_test)

        orig_feature_sets_idxs = self._compute_feature_set_idx(
            vectorizers, 
            feature_sets_dev_orig
        )
        feature_sets_idxs = self._compute_feature_set_idx(
            vectorizers, 
            feature_sets_dev
        )

        print(f'Feature sets computed: {len(feature_sets_dev)}')
        print('\nStacking feature vectors')

        if feature_sets_dev_orig:
            X_dev_stacked_orig = hstacker._hstack(feature_sets_dev_orig)
            X_test_stacked_orig = hstacker._hstack(feature_sets_test_orig)
            print(f'X_dev_stacked_orig shape: {X_dev_stacked_orig.shape}')
            print(f'X_test_stacked_orig shape: {X_test_stacked_orig.shape}')

        X_dev_stacked = hstacker._hstack(feature_sets_dev)
        X_test_stacked = hstacker._hstack(feature_sets_test)

        print(f'X_dev_stacked shape: {X_dev_stacked.shape}')
        print(f'X_test_stacked shape: {X_test_stacked.shape}')

        y_dev_final = y_dev_oversampled if self.config.oversample else y_dev
        y_test_final = y_test_oversampled if self.config.oversample else y_test

        print('\nFeature vectors extracted.\n')
        print(f'Vector document final shape: {X_dev_stacked.shape}')
        print(f"\nX_dev_stacked: {X_dev_stacked.shape[0]}")
        print(f"y_dev: {len(y_dev_final)}")
        print(f"groups_dev: {len(groups_dev)}")
        print(f"groups_dev_orig: {len(orig_groups_dev)}")

        if self.config.oversample:
            return (X_dev_stacked, X_test_stacked, y_dev_final, y_test_final, 
                   groups_dev, feature_sets_idxs, orig_feature_sets_idxs,
                   X_dev_stacked_orig, X_test_stacked_orig, orig_y_dev, 
                   orig_groups_dev)
        else:
            return (X_dev_stacked, X_test_stacked, y_dev_final, y_test_final,
                   groups_dev, feature_sets_idxs, None, None, None, None, None)
                   
    def _compute_feature_set_idx(self, vectorizers, feature_sets_dev):
        """Helper method to compute feature set indices"""
        start_idx = 0
        end_idx = 0
        feature_sets_idxs = {}
        
        for vect, fset in zip(vectorizers, feature_sets_dev):
            if isinstance(fset, list):
                fset = np.array(fset)
            
            if len(fset.shape) == 1:
                fset = fset.reshape(-1, 1)
            
            feature_shape = fset.shape[1]
            end_idx += feature_shape
            feature_sets_idxs[vect] = (start_idx, end_idx)
            start_idx = end_idx
            
        return feature_sets_idxs
    
    def train_model(self, X_dev: np.ndarray, y_dev: List[int], 
                    groups_dev: List[str], model: BaseEstimator, 
                    model_name: str) -> BaseEstimator:
            
        param_grid = {
            'C': np.logspace(-4, 4, 9),
            'class_weight': ['balanced', None]
        }
        
        cv = StratifiedGroupKFold(
            n_splits=5,
            shuffle=True,
            random_state=self.config.random_state
        )
        f1 = make_scorer(f1_score, zero_division=0)
        
        grid_search = GridSearchCV(
            model,
            param_grid=param_grid,
            cv=cv,
            n_jobs=self.config.n_jobs,
            scoring=f1,
            verbose=True
        )
        
        grid_search.fit(X_dev, y_dev, groups=groups_dev)
        print(f'Model fitted. Best params: {grid_search.best_params_}')
        print(f'Best scores: {grid_search.best_score_}\n')
        
        return grid_search.best_estimator_

    def evaluate_model(self, clf: BaseEstimator, X_test: np.ndarray, 
                    y_test: List[int], return_proba: bool = True
                    ) -> Tuple[float, float, np.ndarray, float]:
        
        print('Evaluating performance...',
            '(on fragmented text)' if len(y_test) > 110 else '\n')
        
        y_test = np.array(y_test * X_test.shape[0])
        y_pred = clf.predict(X_test)
        
        if return_proba:
            probabilities = clf.predict_proba(X_test)
            self.posterior_proba = np.median(
                [prob[class_idx] for prob, class_idx in zip(probabilities, y_pred)]
            )
            print(f'Posterior probability: {self.posterior_proba}')
        
        self.accuracy = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, average='binary', zero_division=1.0)
        precision, recall, _, _ = precision_recall_fscore_support(
            y_test, y_pred, average='binary', zero_division=1.0
        )
        print(">>> shape X_test:", X_test.shape)
        print(">>> len y_test:", len(y_test))
        assert len(y_test) == X_test.shape[0], "y_test and X_test must have the same length!"
        cm = confusion_matrix(y_test, y_pred, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()
        cf = np.array([tn, fp, fn, tp])
        
        print(f'Precision: {precision}')
        print(f'Recall: {recall}')
        print(f'Accuracy: {self.accuracy}')
        print(f'F1: {f1}\n')
        print(classification_report(y_test, y_pred, zero_division=1.0))
        print(f'\nConfusion matrix: (tn, fp, fn, tp)\n{cf}\n')
        print(f"Random seed: {self.config.random_state}")
        
        return self.accuracy, f1, cf, self.posterior_proba

    def save_results(self, accuracy: float, f1: float, 
                    posterior_proba: float, cf: np.ndarray, model_name: str, 
                    doc_name: str, features: List[str], 
                    file_name: str, path_name="output.json"):
        
        path = Path(path_name)
        print(f'Saving results in {file_name}\n')
        
        data = {
            'Document test': doc_name,
            'Accuracy': accuracy,
            'Proba': posterior_proba,
            'Confusion matrix': cf
            
        }
        
        output_path = path / file_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data.keys())
            if f.tell() == 0:
                writer.writeheader()
            writer.writerow(data)
        
        print(f"{model_name} results saved in {file_name}\n")


    def run(self, save_results: bool = True, 
            filter_dataset: bool = False):
        """Run the complete epochship verification process"""
        start_time = time.time()
        print(f'Start time: {time.strftime("%H:%M")}')
        print(f'Building LOO model\n')

        documents, epochs, filenames = self.load_dataset()
        
        filenames = [f'{filename}_0' for filename in filenames]

        processed_documents = self.get_processed_documents(documents, filenames)
        
        mapping = {
            'Old Church Slavonic':  1,
            'Church Slavonic':  0,
        }
        
        y = [
            mapping[e.strip()]
            for e in epochs
        ]

        print("Class balance:", np.unique(y, return_counts=True))
        
        test_indices = list(range(len(filenames)))

        for i in test_indices:
            self._process_single_document(
                i, documents, y, processed_documents, filenames, 
                save_results, self.config.results_filename, 
                self.config.results_path  
                )
        
        #ipdb.set_trace()

        total_time = round((time.time() - start_time) / 60, 2)
        print(f'Total time spent for model building: {total_time} minutes.')
    
    def _process_single_document(self, i: int, documents: List[str], y: List[int], 
                              processed_documents: Dict[str, spacy.tokens.Doc],
                              filenames: List[str], save_results: bool,
                              file_name: str, path_name: str):
                                  
        """Process a single document for epochship verification"""
        start_time_single_iteration = time.time()
        np.random.seed(self.config.random_state)
        
        doc, ylabel = documents[i], y[i]
        #ipdb.set_trace()
        X_dev, X_test, y_dev, y_test, groups_dev, groups_test = self.loo_split(
            i, documents, y, doc, ylabel, filenames
        )

        (X_dev, X_test, y_dev, y_test, X_test_frag, y_test_frag, groups_dev, 
         groups_test, groups_test_frag) = self.segment_data(
            X_dev, X_test, y_dev, y_test, groups_dev, groups_test
        )
        print(np.unique(y, return_counts=True))
        #ipdb.set_trace()

        """X_dev_processed = self.get_processed_segments(
            processed_documents, X_dev, groups_dev, dataset='training'
        )
        X_test_processed = self.get_processed_segments(
            processed_documents, X_test, groups_test, dataset='test'
        )
        X_test_frag_processed = self.get_processed_segments(
            processed_documents, X_test_frag, groups_test_frag, 
            dataset='test fragments'
        )"""
        
        X_dev_processed = self.get_processed_segments(
        processed_documents, X_dev, groups_dev, dataset='training'
        )
        # filter None in training
        filtered = [
            (seg, lbl, grp)
            for seg, lbl, grp in zip(X_dev_processed, y_dev, groups_dev)
            if seg is not None
        ]
        if not filtered:
            raise ValueError("Tutti i frammenti di training sono None!")
        X_dev_processed, y_dev, groups_dev = map(list, zip(*filtered))

        X_test_processed = self.get_processed_segments(
            processed_documents, X_test, groups_test, dataset='test'
        )
        # 2) filter None in test
        filtered_test = [
            (seg, lbl)
            for seg, lbl in zip(X_test_processed, y_test)
            if seg is not None
        ]
        if not filtered_test:
            raise ValueError("Tutti i segmenti di test sono None!")
        X_test_processed, y_test = map(list, zip(*filtered_test))

        X_test_frag_processed = self.get_processed_segments(
            processed_documents, X_test_frag, groups_test_frag, 
            dataset='test fragments'
        )
        # filter None in test fragments
        filtered_frag = [
            (seg, lbl, grp)
            for seg, lbl, grp in zip(X_test_frag_processed, y_test_frag, groups_test_frag)
            if seg is not None
        ]
        if filtered_frag:
            X_test_frag_processed, y_test_frag, groups_test_frag = map(list, zip(*filtered_frag))
        else:
            X_test_frag_processed, y_test_frag, groups_test_frag = [], [], []


        X_len = len(X_dev_processed)
        print(f'X_len: {X_len}')
        #ipdb.set_trace()
        
        (X_dev, X_test, y_dev, y_test, groups_dev, feature_idxs, 
         original_feature_idxs, original_X_dev, original_X_test, 
         orig_y_dev, orig_groups_dev) = self.extract_feature_vectors(
            X_dev_processed, X_test_processed, y_dev, y_test, 
            groups_dev
        )

        models = [
            (LogisticRegression(
                random_state=self.config.random_state, 
                n_jobs=self.config.n_jobs
            ), 'Logistic Regressor')
        ]

        for model, model_name in models:
            print(f'\nBuilding {model_name} classifier...\n')
            clf = self.train_model(X_dev, y_dev, groups_dev, model, model_name)
            acc, f1, cf, posterior_proba = self.evaluate_model(
                clf, X_test, y_test
            )

            if save_results:
                self.save_results(acc, f1, posterior_proba, cf, model_name,
                    groups_test[0][:-2], feature_idxs.keys(),
                    file_name, path_name) 

        iteration_time = round((time.time() - start_time_single_iteration) / 60, 2)
        print(f'Time spent for model building for document {groups_test[0][:-2]}: {iteration_time} minutes.')

    

def main():
    config = ModelConfig.from_args()
    #nlp = stanza.Pipeline('cu', processors='tokenize')
    nlp = spacy.load('ru_core_news_lg')
    av_system = EpochshipVerification(config, nlp)
    av_system.run(
        save_results=config.save_res,
        filter_dataset=False,
    )

if __name__ == '__main__':
    main()