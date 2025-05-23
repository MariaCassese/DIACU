import os
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer

from oversampling.dro import DistributionalRandomOversampling
import string
from scipy.sparse import hstack, csr_matrix, issparse
from sklearn.feature_selection import SelectKBest, chi2
from sklearn.preprocessing import Normalizer
import numpy as np
from tqdm import tqdm
import pickle
from nltk import ngrams
#from cltk.prosody.lat.macronizer import Macronizer
#from cltk.prosody.lat.scanner import Scansion

from string import punctuation
import ipdb

class DocumentProcessor:
    def __init__(self, language_model=None, savecache='.cache/processed_docs_def.pkl'):
        self.nlp = language_model
        self.savecache = savecache
        self.init_cache()

    def init_cache(self):
        if self.savecache is None or not os.path.exists(self.savecache):
            print('Cache not found, initializing from scratch')
            self.cache = {}
        else:
            print(f'Loading cache from {self.savecache}')
            self.cache = pickle.load(open(self.savecache, 'rb'))

    def save_cache(self):
        if self.savecache is not None:
            print(f'Storing cache in {self.savecache}')
            parent = Path(self.savecache).parent
            if parent:
                os.makedirs(parent, exist_ok=True)
            pickle.dump(self.cache, open(self.savecache, 'wb'), protocol=pickle.HIGHEST_PROTOCOL)

    def delete_doc(self, filename):
        removed_doc = self.cache.pop(filename, None)
        if removed_doc is not None:
            print(f'Removed {filename} from cache')
            self.save_cache()  # Salva la cache aggiornata dopo l'eliminazione
        
        else:
            print(f'{filename} not found in cache')
            
            
    def process_documents(self, documents, filenames):
        processed_docs = {}
        for filename, doc in zip(filenames, documents):
            if filename in self.cache:
                #print('document already in cache')
                processed_docs[filename[:-2]] = self.cache[filename]
            else:
                print(f'{filename} not in cache')
                processed_doc = self.nlp(doc)
                self.cache[filename] = processed_doc
                processed_docs[filename[:-2]] = self.cache[filename]
                self.save_cache()
        return processed_docs 
    

"""class FeaturesDistortedView:

    def __init__(self, function_words, method, ngram_range=(1,1), **tfidf_kwargs):
        assert method in {'DVEX', 'DVMA', 'DVSA'}, 'text distortion method not valid'
        self.function_words = function_words
        self.ngram_range = ngram_range
        self.tfidf_kwargs = tfidf_kwargs
        self.method = method
        self.counter = CountVectorizer()
        self.vectorizer = TfidfVectorizer(ngram_range=self.ngram_range, **self.tfidf_kwargs)
        self.training_words = []

    def __str__(self) -> str:
        ngram_range_str = f' [n-gram range: {self.ngram_range}]'
        if self.method=='DVEX':
            return 'FeaturesDVEX'+ ngram_range_str
        if self.method=='DVMA':
            return 'FeaturesDVMA'+ ngram_range_str
        if self.method=='DVSA':
            return 'FeaturesDVSA'+ ngram_range_str


    def fit(self, documents, y=None):
        distortions = self.distortion(documents, method=self.method)
        self.vectorizer.fit(distortions)
        return self


    def transform(self, documents, y=None):
        distortions = self.distortion(documents, method=self.method)
        # --- STAMPA DI DEBUG ---
        print(f"\n=== {self.method} – primi 2 documenti distorti ===")
        for i, (orig, dist) in enumerate(zip(documents, distortions)):
            if i >= 2: break
            print(f"Doc {i} ORIGINALE: {orig[:60]}{'...' if len(orig)>60 else ''}")
            print(f"Doc {i} DISTORTO:  {dist[:60]}{'...' if len(dist)>60 else ''}\n")
        self.count_words(distortions)
        features = self.vectorizer.transform(distortions)
        features_num = features.shape[1]
        ipdb.set_trace()
        return features
    

    def fit_transform(self, documents, y=None):
        distortions = self.distortion(documents, method=self.method)
        self.count_words(distortions)
        features = self.vectorizer.fit_transform(distortions)
        #ipdb.set_trace()
        return features
    
    def distortion(self, documents, method):
        if method == 'DVEX':
            dis_texts = self.dis_DVEX(documents)
        elif method =='DVMA':
            dis_texts = self.dis_DVMA(documents)
        elif method =='DVSA':
            dis_texts = self.dis_DVSA(documents)
        #ipdb.set_trace()
        return dis_texts
    
    def count_words(self, texts):
        if not hasattr(self, 'n_training_terms'):
           self.training_words = self.counter.fit_transform(texts) 
           self.n_training_terms = self.training_words.sum(axis=1).getA().flatten()
        else:
            self.test_words = self.counter.transform(texts)
            self.n_test_terms = self.test_words.sum(axis=1).getA().flatten()
        #ipdb.set_trace()



    # DV-MA text distortion method from Stamatatos_2018:
    # Every word not in function_words is masked by replacing each of its characters with an asterisk (*).
    # for character embedding
    def dis_DVMA(self, docs):
        dis_texts = []
        for doc in tqdm(docs, 'DV-MA distorting', total=len(docs)):
            tokens = [str(token) for token in doc]
            dis_text = ''
            for token in tokens:
                if dis_text != '' and token != '.':
                    dis_text += ' '
                if token in self.function_words or token == '.':
                    dis_text += token
                else:
                    dis_text += '*' * len(token)
            dis_texts.append(dis_text)
            #ipdb.set_trace()
        return dis_texts
    
    
    # DV-SA text distortion method from Stamatatos_2018:
    # Every word not in function_words is replaced with an asterisk (*).
    # for character embedding
    def dis_DVSA(self, docs):
        dis_texts = []
        for doc in tqdm(docs, 'DV-SA distorting', total=len(docs)):
            tokens = [str(token) for token in doc]
            dis_text = ''
            for token in tokens:
                if dis_text != '' and token != '.':
                    dis_text += ' '
                if token in self.function_words or token == '.':
                    dis_text += token
                else:
                    dis_text += '*'
            dis_texts.append(dis_text)
            #ipdb.set_trace()
        return dis_texts
    

    # DV-EX text distortion method from Stamatatos_2018:
    # Every word not in function_words is masked by replacing each of its characters with an asterisk (*),
    # except first and last one.
    # Words of len 2 or 1 remain the same.
    def dis_DVEX(self, documents):

        def DVEX(token):
            if len(token) <= 2:
                return token
            return token[0] + ('*' * (len(token) - 2)) + token[-1]

        dis_texts = []
        for doc in tqdm(documents, 'DV-EX distorting', total=len(documents)):
            tokens = [str(token) for token in doc]
            dis_text = [token if token in self.function_words else DVEX(token) for token in tokens]
            # for token in tokens:
            #     if token in self.function_words:
            #         dis_text.append(token)
            #     else:
            #         dis_text.append(DVEX(token))
            dis_texts.append(' '.join(dis_text))
            #ipdb.set_trace()

        return dis_texts"""
    
        

"""class FeaturesSyllabicQuantities:

    def __init__(self, min_range=1,max_range=1, ngram_range=(1,1), **tfidf_kwargs):
        self.tfidf_kwargs = tfidf_kwargs
        self.min_range = min_range
        self.max_range = max_range
        self.ngram_range = ngram_range
        self.vectorizer = TfidfVectorizer(ngram_range=self.ngram_range, **self.tfidf_kwargs)
        self.counter = CountVectorizer()
        

    def __str__(self) -> str:
        ngram_range_str = f' [n-gram range: {self.ngram_range}]'
        return 'FeaturesSyllabicQuantities' + ngram_range_str


    def fit(self, documents, y=None):
        raw_documents = [doc.text for doc in documents]
        scanned_texts = self.metric_scansion(documents)
        #self.count_syllabic_quantities(scanned_texts)
        #self.vectorizer = TfidfVectorizer(**self.tfidf_kwargs)
        self.vectorizer.fit(scanned_texts)
        return self


    def transform(self, documents, y=None):
        raw_documents = [doc.text for doc in documents]
        scanned_texts = self.metric_scansion(documents)
        self.count_syllabic_quantities(scanned_texts)
        features = self.vectorizer.transform(scanned_texts)
        return features
    

    def fit_transform(self, documents, y=None):
        raw_documents = [doc.text for doc in documents]
        scanned_texts = self.metric_scansion(documents)
        self.count_syllabic_quantities(scanned_texts)
        # self.vectorizer = TfidfVectorizer(**self.tfidf_kwargs)
        features = self.vectorizer.fit_transform(scanned_texts)
        return features
    

    def metric_scansion(self, documents, filenames=None):
        #documents = [self.remove_invalid_word(doc, filename) for doc, filename in zip(documents, filenames)]
        documents = [self.remove_invalid_word(doc) for doc in documents]
            
        macronizer = Macronizer('tag_ngram_123_backoff')
        scanner = Scansion(
            clausula_length=100000, punctuation=string.punctuation)  # clausula_length was 13, it didn't get the string before that point (it goes backward)
        macronized_texts = [macronizer.macronize_text(doc) for doc in tqdm(documents, 'macronizing', total=len(documents))]
        scanned_texts = [scanner.scan_text(doc) for doc in
                        tqdm(macronized_texts, 'metric scansion', total=len(macronized_texts))]
        scanned_texts = [''.join(scanned_text) for scanned_text in scanned_texts]  # concatenate the sentences
        return scanned_texts
    
    def remove_invalid_word(self, document, filename=None):
        # todo: salvare i numeri romani, i numeri
        legal_words=[]
        vowels = set('aeiouāēīōū')
        tokens = [token.text for token in document]
        illegal_tokens=[]

        for token in tokens:
            token = token.lstrip()
            if len(token) == 1:
                if token.lower() in vowels or token in punctuation:
                    legal_words.append(token)
            elif len(token) == 2:
                if not all(char in punctuation for char in token) and not all(char not in vowels for char in token): 
                    legal_words.append(token)
            else:
                if (
                    any(char in vowels for char in token)
                    and not any(
                        token[i] in punctuation and token[i + 1] in punctuation
                        for i in range(len(token) - 1)
                    )
                ):
                    legal_words.append(token)

            if token not in legal_words:
                illegal_tokens.append(token)
        
        if filename:

            with open("illegal_words.txt", "a") as file:
                file.write(f"{filename}\n")
                file.write(f"{str(document)[:50]}\n")
                file.write(f"{illegal_tokens}\n")
                file.write("\n")
                

        return ' '.join(legal_words)


    def count_syllabic_quantities(self, texts):
        if not hasattr(self, 'n_training_terms'):
            self.training_words = self.counter.fit_transform(texts) 
            self.n_training_terms = self.training_words.sum(axis=1).getA().flatten()
        else:
            self.test_words = self.counter.transform(texts)
            self.n_test_terms = self.test_words.sum(axis=1).getA().flatten()"""


class DummyTfidf:

    def __init__(self,upto, feature_type="word"):
        assert feature_type in {'word', 'sentence'}, 'feature type not valid'
        self.upto = upto
        self.prefix = f"{feature_type}_length" 

    def get_feature_names_out(self):
        return np.array([f"{self.prefix}_{i}" for i in range(1, self.upto)])


class FeaturesMendenhall:
    """
    Extract features as the frequency of the words' lengths used in the documents,
    following the idea behind Mendenhall's Characteristic Curve of Composition
    """
    def __init__(self,upto=25):
        self.upto = upto
        self.vectorizer = DummyTfidf(self.upto)

    def __str__(self) -> str:
        return 'FeaturesMendenhall'

    def fit(self, documents, y=None):
        return self

    def transform(self, documents, y=None):
        features = []
        for doc in tqdm(documents, 'Extracting word lenghts', total=len(documents)):
            word_lengths = [len(str(token)) for token in doc]
            hist = np.histogram(word_lengths, bins=np.arange(1, self.upto), density=True)[0]
            distribution = np.cumsum(hist)
            features.append(distribution)
            #ipdb.set_trace()
        return np.asarray(features)

    def fit_transform(self, documents, y=None):
        return self.fit(documents).transform(documents)


class FeaturesSentenceLength:
    def __init__(self, upto=1000, language='russian'):
        self.upto = upto
        self.language = language
        self.vectorizer = DummyTfidf(self.upto)

    def __str__(self) -> str:
        return 'FeaturesSentenceLength'

    def fit(self, documents, y=None):
        return self

    def transform(self, documents, y=None):
        features = []
        for doc in tqdm(documents, 'Extracting sentence lenghts', total=len(documents)):
            sentence_lengths = []
            for sentence in doc.sents:
                sent_len = [len(str(token)) for token in sentence]
                sentence_lengths += sent_len
            hist = np.histogram(sentence_lengths, bins=np.arange(1, self.upto), density=True)[0]
            distributuion = np.cumsum(hist)
            features.append(distributuion)
        return np.asarray(features)

    def fit_transform(self, documents, y=None):
        return self.fit(documents).transform(documents)


class FeaturesCharNGram:

    def __init__(self, n=(1,3), sublinear_tf=False, norm='l1'):
        self.n = n
        self.sublinear_tf = sublinear_tf
        self.norm = norm
        self.counter = CountVectorizer(analyzer='char', ngram_range=self.n, min_df=3)
        self.vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(self.n), use_idf=False, norm=self.norm, min_df=3)
        #ipdb.set_trace()
    
    def __str__(self) -> str:
        return f'FeaturesCharNGram [n-gram range: ({self.n[0]},{self.n[1]})]'

    def fit(self, documents, y=None):
        raw_documents = [doc.text for doc in documents]
        self.vectorizer.fit(raw_documents)
        #ipdb.set_trace()
        return self

    def transform(self, documents, y=None):
        raw_documents = [doc.text for doc in documents]
        self.count_ngrams(raw_documents)
        return self.vectorizer.transform(raw_documents)

    def fit_transform(self, documents, y=None):
        raw_documents = [doc.text for doc in documents]
        self.count_ngrams(raw_documents)
        self.vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(self.n), use_idf=False, norm=self.norm, min_df=3)
        #ipdb.set_trace()
        return self.vectorizer.fit_transform(raw_documents)

    
    def count_ngrams(self, texts):
        if not hasattr(self, 'n_training_terms'):
            self.training_ngrams = self.counter.fit_transform(texts)
            self.n_training_terms = self.training_ngrams.sum(axis=1).getA().flatten()
            #ipdb.set_trace()
        else:
            self.test_ngrams = self.counter.transform(texts)
            self.n_test_terms = self.test_ngrams.sum(axis=1).getA().flatten()
            


"""class FeaturesFunctionWords:

    def __init__(self, use_idf=False, sublinear_tf=False, norm='l1', ngram_range=(1,3)): #function_words,
        self.use_idf = use_idf
        self.sublinear_tf = sublinear_tf
        self.norm = norm
        self.ngram_range=ngram_range
        self.counter = CountVectorizer(vocabulary=self.function_words, min_df=1)
        self.vectorizer = TfidfVectorizer(
            vocabulary=self.function_words, use_idf=self.use_idf, sublinear_tf=self.sublinear_tf, norm=self.norm, ngram_range=self.ngram_range)
    
    def __str__(self) -> str:
        ngram_range_str = f' [n-gram range: {self.ngram_range}]'
        return 'FeaturesFunctionWords' + ngram_range_str

    def fit(self, documents, y=None):
        raw_documents = [doc.text for doc in documents]
        self.vectorizer.fit(raw_documents)
        return self

    def transform(self, documents, y=None):
        raw_documents = [doc.text for doc in documents]
        self.count_words(raw_documents)
        return self.vectorizer.transform(raw_documents)

    def fit_transform(self, documents, y=None):
        raw_documents = [doc.text for doc in documents]
        self.count_words(raw_documents)  
        features = self.vectorizer.fit_transform(raw_documents)
        return features
    
    def count_words(self, texts):
        if not hasattr(self, 'n_training_terms'):
            self.training_words = self.counter.fit_transform(texts)
            self.n_training_terms = self.training_words.sum(axis=1).getA().flatten()
        else:
            # Trasforma i nuovi testi e calcola il numero di n-grams
            self.test_words = self.counter.transform(texts)
            self.n_test_terms = self.test_words.sum(axis=1).getA().flatten()


class FeaturesVerbalEndings:

    def __init__(self, verbal_endings, n=(1,1), extract_longest_match=False, use_idf=True, sublinear_tf=True, norm='l2', **tfidf_kwargs):
        self.use_idf = use_idf
        self.sublinear_tf = sublinear_tf
        self.norm = norm
        self.tfidf_kwargs = tfidf_kwargs
        self.n = n
        self.verbal_endings=verbal_endings
        self.extract_longest_match=extract_longest_match
        self.counter = CountVectorizer(analyzer=self.endings_analyzer, vocabulary=self.verbal_endings)
        self.vectorizer = TfidfVectorizer(analyzer=self.endings_analyzer, vocabulary=self.verbal_endings, use_idf=self.use_idf, sublinear_tf=self.sublinear_tf, norm=self.norm, **self.tfidf_kwargs)
        

    def __str__(self) -> str:
        return 'FeaturesVerbalEndings'
    

    def fit(self, documents, y=None):
        self.count_words(documents)   
        self.vectorizer.fit(documents)
        return self

    def transform(self, documents, y=None):
        self.count_words(documents)
        endings_features = self.vectorizer.transform(documents)
        return endings_features

    def fit_transform(self, documents, y=None):
        self.count_words(documents)
        endings_features = self.vectorizer.fit_transform(documents)
        return endings_features


    def endings_analyzer(self, doc):
        ngram_range = self.tfidf_kwargs.get('ngram_range', self.n) # up to quadrigrams
        ngram_range = slice(*ngram_range)
        doc_endings = []
        
        for sentence in doc.sents:
            sent_endings = []
            sentence_unigram_verbs = [token.text.lower() for token in sentence if token.pos_ == 'VERB']
            matching_endings = [ending for ending in self.verbal_endings if any(verb.endswith(ending) for verb in sentence_unigram_verbs)]
            if matching_endings:
                if self.extract_longest_match:
                    sent_endings.append(max(matching_endings, key=len))
                else:
                    sent_endings.extend(matching_endings)

            for n in list(range(ngram_range.start, ngram_range.stop+1)):
                sentence_ngram_endings = ['-'.join(ngram) for ngram in list(ngrams(sent_endings, n))]
                doc_endings.extend(sentence_ngram_endings)
        return doc_endings

    def count_words(self, documents):
        if not hasattr(self, 'n_training_terms'):
            self.training_words = self.counter.fit_transform(documents)
            self.n_training_terms = self.training_words.sum(axis=1).getA().flatten()
        else:
            self.test_words = self.counter.transform(documents)
            self.n_test_terms = self.test_words.sum(axis=1).getA().flatten()"""

        

class FeaturesPunctuation:

    def __init__(self, sublinear_tf=False, norm='l1', ngram_range=(1,3)):
        self.sublinear_tf = sublinear_tf
        self.norm = norm
        self.punctuation=punctuation
        self.ngram_range = ngram_range
        self.counter = CountVectorizer(vocabulary=self.punctuation, min_df=1)
        self.vectorizer = TfidfVectorizer(analyzer='char', vocabulary=self.punctuation, use_idf=False, norm=self.norm, min_df=3, ngram_range=self.ngram_range)
    
    def __str__(self) -> str:
        ngram_range_str = f' [n-gram range: {self.ngram_range}]'
        return 'FeaturesPunctuation' + ngram_range_str

    def fit(self, documents, y=None):
        raw_documents = [doc.text for doc in documents]
        self.vectorizer.fit(raw_documents)
        return self

    def transform(self, documents, y=None):
        raw_documents = [doc.text for doc in documents]
        self.count_words(raw_documents)
        return self.vectorizer.transform(raw_documents)

    def fit_transform(self, documents, y=None):
        raw_documents = [doc.text for doc in documents]
        self.count_words(raw_documents)
        return self.vectorizer.fit_transform(raw_documents)

    def count_words(self, texts):
        if not hasattr(self, 'n_training_terms'):
            self.training_words = self.counter.fit_transform(texts)
            self.n_training_terms = self.training_words.sum(axis=1).getA().flatten()
        else:
            self.test_words = self.counter.transform(texts)
            self.n_test_terms = self.test_words.sum(axis=1).getA().flatten()


class FeaturesPOST:
    def __init__(self, n=(1,4), use_idf=True, sublinear_tf=True, norm='l2', savecache='.postcache/dict.pkl', **tfidf_kwargs):
        self.use_idf = use_idf
        self.sublinear_tf = sublinear_tf
        self.norm = norm
        self.tfidf_kwargs = tfidf_kwargs
        self.savecache = savecache
        self.n = n
        self.counter = CountVectorizer(analyzer=self.post_analyzer)
        self.vectorizer = TfidfVectorizer(analyzer=self.post_analyzer, use_idf=self.use_idf, sublinear_tf=self.sublinear_tf, norm=self.norm, **self.tfidf_kwargs)
        #ipdb.set_trace()
    

    def __str__(self) -> str:
        return f'FeaturesPOST [n-gram range: ({self.n[0]},{self.n[1]})]'


    def post_analyzer(self, doc):
        ngram_range = self.tfidf_kwargs.get('ngram_range', (self.n)) # up to quadrigrams
        ngram_range = slice(*ngram_range)
        ngram_tags = []
        
        for sentence in doc.sents:
            sentence_unigram_tags = [token.pos_ if token.pos_ != '' else 'Unk' for token in sentence]
            for n in list(range(ngram_range.start, ngram_range.stop+1)):
                sentence_ngram_tags = ['-'.join(ngram) for ngram in list(ngrams(sentence_unigram_tags, n))]
                ngram_tags.extend(sentence_ngram_tags)
        #ipdb.set_trace()
        return ngram_tags


    def fit(self, documents, y=None):
        self.count_pos_tags(documents)
        self.vectorizer.fit(documents)
        return self

    def transform(self, documents, y=None):
        self.count_pos_tags(documents)
        post_features = self.vectorizer.transform(documents)
        print("=== FeaturesPOST.transform ===")
        print("shape:", post_features.shape)
        # stampa i primi 5 POS-n-gram (colonne) effettivamente NON NULLI nel doc 0
        row0 = post_features[0]
        nz_cols = row0.nonzero()[1]
        print("non-zero cols in row 0:", nz_cols[:5])
        # ottieni i nomi di quegli n-grammi POS
        feature_names = self.vectorizer.get_feature_names_out()
        print("example features:", [feature_names[i] for i in nz_cols[:5]])
        print("first 5 values:", row0.data[:5])
        print("===============================")
        #ipdb.set_trace()
        return post_features

    def fit_transform(self, documents, y=None):
        self.count_pos_tags(documents)
        post_features = self.vectorizer.fit_transform(documents)
                # ───> stesso controllo in fase di fit_transform
        print("=== FeaturesPOST.fit_transform ===")
        print("shape:", post_features.shape)
        # es. prima riga
        row0 = post_features[0]
        nz = row0.nonzero()[1]
        print("ex POS-n-grams:", [self.vectorizer.get_feature_names_out()[i] for i in nz[:5]])
        print("vals:", row0.data[:5])
        print("===============================")
        #ipdb.set_trace()
        return post_features

    def count_pos_tags(self, documents):
        if not hasattr(self, 'n_training_terms'):
            self.training_words = self.counter.fit_transform(documents)
            self.n_training_terms = self.training_words.sum(axis=1).getA().flatten()
            #ipdb.set_trace()
        else:
            self.test_words = self.counter.transform(documents)
            self.n_test_terms = self.test_words.sum(axis=1).getA().flatten()
            #ipdb.set_trace()
    

class FeaturesDEP:
    def __init__(self, n=(1,3), use_idf=True, sublinear_tf=True, norm='l2', savecache='.depcache/dict.pkl', **tfidf_kwargs):
        self.use_idf = use_idf
        self.sublinear_tf = sublinear_tf
        self.norm = norm
        self.tfidf_kwargs = tfidf_kwargs
        self.savecache = savecache
        self.n = n
        self.counter = CountVectorizer(analyzer=self.dep_analyzer)
        self.vectorizer = TfidfVectorizer(analyzer=self.dep_analyzer, use_idf=self.use_idf, sublinear_tf=self.sublinear_tf, norm=self.norm, **self.tfidf_kwargs)
        #ipdb.set_trace()
    
    def __str__(self) -> str:
        return f'FeaturesDEP [n-gram range: ({self.n[0]},{self.n[1]})]'
    

    def dep_analyzer(self, doc):
        ngram_range = self.tfidf_kwargs.get('ngram_range', (self.n))
        ngram_range = slice(*ngram_range)
        ngram_deps = []
        #ipdb.set_trace()

        for sentence in doc.sents:
            sentence_unigram_deps = [token.dep_ if token.dep_ != '' else 'Unk' for token in sentence] #.split(':')[0]
            for n in list(range(ngram_range.start, ngram_range.stop+1)):
                sentence_ngram_deps = ['-'.join(ngram) for ngram in list(ngrams(sentence_unigram_deps, n))]
                ngram_deps.extend(sentence_ngram_deps)
                #ipdb.set_trace()
        return ngram_deps


    def fit(self, documents, y=None):
        self.vectorizer.fit(documents)
        return self

    def transform(self, documents, y=None):
        self.count_deps(documents)
        dep_features = self.vectorizer.transform(documents)
        features_num =dep_features.shape[1]
        #ipdb.set_trace()
        return dep_features

    def fit_transform(self, documents, y=None):
        self.count_deps(documents)
        dep_features = self.vectorizer.fit_transform(documents)
        #ipdb.set_trace()

        return dep_features
    
    def count_deps(self, documents):
        if not hasattr(self, 'n_training_terms'):
            self.training_words = self.counter.fit_transform(documents)
            self.n_training_terms = self.training_words.sum(axis=1).getA().flatten()
            #ipdb.set_trace()
        else:
            self.test_words = self.counter.transform(documents)
            self.n_test_terms = self.test_words.sum(axis=1).getA().flatten()
            #ipdb.set_trace()

    
class FeatureSetReductor:
    def __init__(self, feature_extractor, measure=chi2, k=5000, k_ratio=1.0, normalize=True, oversample=True):
        self.feature_extractor = feature_extractor
        self.k = k
        self.k_ratio = k_ratio
        self.measure = measure
        self.normalize = normalize 
        self.oversample = oversample
        self.is_sparse = True
        if self.normalize:
            self.normalizer = Normalizer()
        
    def __str__(self) -> str:
        return( f'FeatureSetReductor for {self.feature_extractor}' )


    def fit(self, documents, y_dev=None):
        return self.feature_extractor.fit(documents, y_dev)

    def transform(self, documents, y_dev=None):
        matrix = self.feature_extractor.transform(documents)
        #ipdb.set_trace()

        if self.normalize:
            matrix_norm  = self.normalizer.transform(matrix) 
            matrix_red = self.feat_sel.transform(matrix_norm)
            #ipdb.set_trace()
        else:
            matrix_red = self.feat_sel.transform(matrix, y_dev)
            #ipdb.set_trace()
        return matrix_red 

    def fit_transform(self, documents, y_dev=None):
        matrix = self.feature_extractor.fit_transform(documents, y_dev)
        self.features_in = matrix.shape[1]
        #ipdb.set_trace()

        if self.features_in < self.k:
            self.k = self.features_in
            #ipdb.set_trace()
        else:
            #self.k = round(features_in * 0.1) #keep 10% of features
            self.k = round(self.features_in * self.k_ratio) #keep k_ratio% of features
            #ipdb.set_trace()

        self.feat_sel = SelectKBest(self.measure, k=self.k)
        print('features in:', self.features_in, 'k:', self.k)
        print()
        #ipdb.set_trace()

        if self.normalize:
            matrix_norm  = self.normalizer.fit_transform(matrix, y_dev)
            matrix_red = self.feat_sel.fit_transform(matrix_norm, y_dev)
            #ipdb.set_trace()
            
        else:
            matrix_red = self.feat_sel.fit_transform(matrix, y_dev)
            #ipdb.set_trace()

        return matrix_red
    
    def oversample_DRO(self, Xtr, ytr, Xte, yte, groups=None, rebalance_ratio=0.2, test_samples=100):
        if not isinstance(ytr, np.ndarray):
            ytr = np.array(ytr)
        self.dro = DistributionalRandomOversampling(rebalance_ratio=rebalance_ratio)
        samples = self.dro._samples_to_match_ratio(ytr)
        original_indices = self.dro.get_original_indices(Xtr, samples)
        y_oversampled = self.dro._oversampling_observed(ytr, samples)
        Xtr_old = Xtr.copy()
        #ipdb.set_trace()

        if groups:
            groups = [group.split('_0')[0] for group in groups]
            groups_oversampled = []
            for group, i in zip(groups, samples):
                groups_oversampled.extend([group]*i)
                #ipdb.set_trace()

        n_examples = samples.sum() - len(ytr)
        #ipdb.set_trace()

        if hasattr(self.feature_extractor, 'n_training_terms'):
            print('Oversampling positive class using DRO method')
            self.n_training_terms =  self.feature_extractor.n_training_terms
            self.n_test_terms = self.feature_extractor.n_test_terms
            #ipdb.set_trace()

            positives = ytr.sum()
            nD = len(ytr) 
            #ipdb.set_trace()

            print('Before oversampling')
            print(f'positives = {positives} (prevalence={positives*100/nD:.2f}%)')
            #ipdb.set_trace()

            Xtr, ytr = self.dro.fit_transform(Xtr, ytr, self.n_training_terms)
            Xte = self.dro.transform(Xte, self.n_test_terms, samples=test_samples) #new
            #ipdb.set_trace()

            positives = ytr.sum()
            nD = len(ytr)
            print('After oversampling')
            print(f'positives = {positives} (prevalence={positives*100/nD:.2f}%)')
            print(Xtr.shape, len(ytr))
            print(Xte.shape)
            #ipdb.set_trace()
        
        else:
            print('Duplicating vectors to match oversampled data')
            print('Type of Xtr and Xte', type(Xtr), type(Xte))

            Xtr = [Xtr[i] for i in original_indices]
            ytr = [ytr[i] for i in original_indices]

            Xtr = np.array(Xtr)
            Xte = np.array(Xte)
            
            if len(Xtr.shape) == 1:
                Xtr = Xtr.reshape(-1, 1)
            
             # Oversample Xte and yte to match test_samples
            Xte = np.tile(Xte, (test_samples, 1))  # Duplicate Xte to match test_samples
            yte = np.array([yte] * test_samples)  # Duplicate yte to match test_samples
            #ipdb.set_trace()
            
           

            print(Xtr.shape, len(ytr))
            print(Xte.shape)

        return Xtr, ytr, Xte, yte, groups_oversampled


class HstackFeatureSet:
    def __init__(self, feats=None, *vectorizers):
        self.vectorizers = vectorizers

    def fit(self, documents, authors=None):
        for v in self.vectorizers:
            v.fit(documents, authors)
        return self

    def transform(self, documents, authors=None):
        feats = [v.transform(documents, authors) for v in self.vectorizers]
        return self._hstack(feats)

    def fit_transform(self, documents, authors=None):
        feats = [v.fit_transform(documents, authors) for v in self.vectorizers]
        return self._hstack(feats)

    def _hstack(self, feats):
        for i, f in enumerate(feats):
            if not issparse(f):
                if not (isinstance(f, np.ndarray) and f.dtype == np.float64): 
                    feats[i] = np.asarray(f).astype(np.float64)

        anysparse = any(map(issparse, feats))
        if anysparse:
            feats = [csr_matrix(f) for f in feats]
            feats = hstack(feats)
        else:
            feats = np.hstack(feats)
        #ipdb.set_trace()
        return feats