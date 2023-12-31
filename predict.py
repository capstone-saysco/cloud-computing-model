from __future__ import absolute_import, division, print_function, unicode_literals

import tensorflow as tf
import numpy as np

from tensorflow import keras
from keras.layers import Layer
from keras import backend as K
from keras.models import load_model
import re
import nltk
nltk.download('punkt')
import pickle

class ZeroMaskedEntries(Layer):
    """
    This layer is called after an Embedding layer.
    It zeros out all of the masked-out embeddings.
    It also swallows the mask without passing it on.
    You can change this to default pass-on behavior as follows:

    def compute_mask(self, x, mask=None):
        if not self.mask_zero:
            return None
        else:
            return K.not_equal(x, 0)
    """

    def __init__(self, mask_zero=False, **kwargs):
        super(ZeroMaskedEntries, self).__init__(**kwargs)
        self.mask_zero = mask_zero

    def build(self, input_shape):
        self.output_dim = input_shape[1]
        self.repeat_dim = input_shape[2]

    def call(self, inputs, mask=None):
        mask = K.cast(mask, 'float32')
        mask = K.repeat(mask, self.repeat_dim)
        mask = K.permute_dimensions(mask, (0, 2, 1))
        return inputs * mask

    def compute_mask(self, inputs, mask=None):
        if not self.mask_zero:
            return None
        else:
            return tf.not_equal(inputs, 0)
    
    def get_config(self):
        base_config = super(ZeroMaskedEntries, self).get_config()
        config = {'mask_zero': keras.saving.serialize_keras_object(self.mask_zero)}
        return dict(list(base_config.items()) + list(config.items()))
    
class Attention(Layer):
    def __init__(self, op='attsum', activation='tanh', init_stdev=0.01, **kwargs):
        self.supports_masking = True
        assert op in {'attsum', 'attmean'}
        assert activation in {None, 'tanh'}
        self.op = op
        self.activation = activation
        self.init_stdev = init_stdev
        super(Attention, self).__init__(**kwargs)

    def build(self, input_shape):
        init_val_v = (np.random.randn(input_shape[2]) * self.init_stdev).astype(K.floatx())
        self.att_v = tf.Variable(init_val_v, name='att_v', trainable=True)
        init_val_W = (np.random.randn(input_shape[2], input_shape[2]) * self.init_stdev).astype(K.floatx())
        self.att_W = tf.Variable(init_val_W, name='att_W', trainable=True)

    def call(self, inputs, mask=None):
        y = K.dot(inputs, self.att_W)
        if not self.activation:
            weights = tf.tensordot(self.att_v, y, axes=[0, 2])
        elif self.activation == 'tanh':
            weights = tf.tensordot(self.att_v, K.tanh(y), axes=[[0], [2]])

        weights = K.softmax(weights)

        out = inputs * K.permute_dimensions(K.repeat(weights, inputs.shape[2]), [0, 2, 1])
        if self.op == 'attsum':
            # out = out.sum(axis=1)
            out = K.sum(out, axis=1)
        elif self.op == 'attmean':
            out = out.sum(axis=1) / mask.sum(axis=1, keepdims=True)
        return K.cast(out, K.floatx())

    def compute_output_shape(self, input_shape):
        return (input_shape[0], input_shape[2])

    def compute_mask(self, x, mask):
        return None

    def get_config(self):
        config = {'op': self.op, 'activation': self.activation, 'init_stdev': self.init_stdev}
        base_config = super(Attention, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))

def tokenizer(text):
    text = re.sub('(http[s]?://)?((www)\.)?([a-zA-Z0-9]+)\.{1}((com)(\.(cn))?|(org))', '<url>', text) # remove links
    text = re.sub(r'\.{3,}(\s+\.{3,})*', '...', text) # ellipsis handling (..., ???, !!!) --> (., ?. !)
    text = re.sub(r'\?{2,}(\s+\?{2,})*', '?', text) 
    text = re.sub(r'\!{2,}(\s+\!{2,})*', '!', text)

    # tokenization with NLTK, creating list of words & punctuation
    tokens = nltk.word_tokenize(text)

    for index, token in enumerate(tokens):
        if token == '@' and (index+1) < len(tokens):
            tokens[index+1] = '@' + re.sub('[0-9]+.*', '', tokens[index+1])
            tokens.pop(index)

    # rejoining tokens : token list --> string
    text = " ".join(tokens)
    
    # call tokenize_to_sentences function
    sent_tokens = tokenize_to_sentences(text, max_sentlength=50)

    return sent_tokens  

def tokenize_to_sentences(text, max_sentlength):
    # split text into sentences
    sents = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\!|\?)\s', text)

    processed_sents = []

    # iterate through sentences
    for sent in sents:
        if re.search(r'(?<=\.{1}|\!|\?|\,)(@?[A-Z]+[a-zA-Z]*[0-9]*)', sent):
            s = re.split(r'(?=.{2,})(?<=\.{1}|\!|\?|\,)(@?[A-Z]+[a-zA-Z]*[0-9]*)', sent)
            ss = " ".join(s)
            ssL = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\!|\?)\s', ss)
            processed_sents.extend(ssL)
        else:
            processed_sents.append(sent)
    
    sent_tokens = []
    for sent in processed_sents:
        shorten_sents_tokens = shorten_sentence(sent, max_sentlength)
        sent_tokens.extend(shorten_sents_tokens)

    return sent_tokens

def shorten_sentence(sent, max_sentlen):
    new_tokens = []
    sent = sent.strip()
    tokens = nltk.word_tokenize(sent)
    if len(tokens) > max_sentlen: # if tokens larger than maximum sentence length, shorten it
        split_keywords = ['because', 'but', 'so', 'You', 'He', 'She', 'We', 'It', 'They', 'Your', 'His', 'Her']
        k_indexes = [i for i, key in enumerate(tokens) if key in split_keywords]
        processed_tokens = []
        if not k_indexes:
            num = (int) (len(tokens) / max_sentlen)
            k_indexes = [(i+1)*max_sentlen for i in range(num)]

        processed_tokens.append(tokens[0:k_indexes[0]])
        len_k = len(k_indexes)
        for j in range(len_k-1):
            processed_tokens.append(tokens[k_indexes[j]:k_indexes[j+1]])
        processed_tokens.append(tokens[k_indexes[-1]:])

        for token in processed_tokens:
            if len(token) > max_sentlen:
                num = (int) (len(token) / max_sentlen)
                s_indexes = [(i+1)*max_sentlen for i in range(num)]

                len_s = len(s_indexes)
                new_tokens.append(token[0:s_indexes[0]])
                for j in range(len_s-1):
                    new_tokens.append(token[s_indexes[j]:s_indexes[j+1]])
                new_tokens.append(token[s_indexes[-1]:])

            else:
                new_tokens.append(token)
    else: # if not, just return
        return [tokens]

    return new_tokens

def fit_tokenizer(essays, vocab):
    data_x, text = [], []
    num_hit, unk_hit, punc_hit, total = 0., 0., 0., 0.
    max_sentnum = -1 # maximum num of sentences
    max_sentlen = -1 # maximum sentence length

    num_regex = re.compile('^[+-]?[0-9]+\.?[0-9]*$')
    punc_regex = re.compile(r'[^\w\s]')

    for content in essays:
        sent_tokens = tokenizer(content) # transform individual essays into sentence tokens
        sent_tokens = [[w.lower() for w in s] for s in sent_tokens]

        sent_indices = [] 
        indices = []
        sentences = []
        words = []

        for sent in sent_tokens: # iterate through sentences in sent_tokens
            length = len(sent)
            
            if length > 0:
                if max_sentlen < length:
                    max_sentlen = length
                
                for word in sent: # iterate through words in each sentence
                    if bool(num_regex.match(word)): # if "word" is number, turn in into <num> index (2)
                        indices.append(vocab['<num>'])
                        num_hit += 1
                    elif bool(punc_regex.match(word)):
                        indices.append(vocab['<pad>'])
                        punc_hit += 1
                    elif word in vocab: # if "word" is in vocab, turn it into the word's index in vocab
                        indices.append(vocab[word])
                    else:
                        indices.append(vocab['<unk>'])
                        unk_hit += 1
                    total += 1
                    words.append(word)
                sentences.append(words)
                sent_indices.append(indices)
                indices = []
                words = []
        
        data_x.append(sent_indices)

        if max_sentnum < len(sent_indices):
            max_sentnum = len(sent_indices)
        
    return data_x

def sequence_and_padding(index_sequences, max_sentnum, max_sentlen):
    X = np.empty([len(index_sequences), max_sentnum, max_sentlen], dtype=np.int32)

    for i in range(len(index_sequences)):
        sequence_ids = index_sequences[i]
        num = len(sequence_ids)

        for j in range(num):
            word_ids = sequence_ids[j]
            length = len(word_ids)
            for k in range(length):
                wid = word_ids[k]
                X[i, j, k] = wid

            X[i, j, length:] = 0

        X[i, num:, :] = 0
    
    return X

def build_model():
    model = load_model(
        "./assets/model_capstone.h5",
        custom_objects={
            "ZeroMaskedEntries": ZeroMaskedEntries, 
            "Attention": Attention
            }
        )

    model.summary()
    return model

def make_prediction(input_data):
    with open('./assets/saved_vocab.pkl', 'rb') as f:
        vocab = pickle.load(f)
    model = build_model()
    input_tokenized = fit_tokenizer(input_data, vocab)
    input_sequenced_padded = sequence_and_padding(input_tokenized, max_sentnum=25, max_sentlen=50)
    input_sequenced_padded_reshaped = input_sequenced_padded.reshape((input_sequenced_padded.shape[0], input_sequenced_padded.shape[1] * input_sequenced_padded.shape[2]))
    result = model.predict(input_sequenced_padded_reshaped)
    return result








