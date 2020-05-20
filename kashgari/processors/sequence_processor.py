# encoding: utf-8

# author: BrikerMan
# contact: eliyar917@gmail.com
# blog: https://eliyar.biz

# file: text_processor.py
# time: 12:27 下午

import collections
import logging
import operator
from typing import Dict, List, Any, Optional

import numpy as np
import tqdm
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.utils import to_categorical

from kashgari.generators import CorpusGenerator
from kashgari.processors.abc_processor import ABCProcessor
from kashgari.types import TextSamplesVar


class SequenceProcessor(ABCProcessor):
    """
    Generic processors for the sequence samples.
    """

    def info(self) -> Dict:
        data = super(SequenceProcessor, self).info()
        data['config'].update({
            'build_in_vocab': self.build_in_vocab,
            'min_count': self.min_count,
            'allow_unk': self.allow_unk
        })
        return data

    def __init__(self,
                 build_in_vocab: str = 'text',
                 min_count: int = 3,
                 build_vocab_from_labels: bool = False,
                 **kwargs: Any) -> None:
        """

        Args:
            vocab_dict_type: initial vocab dict type, one of `text` `labeling`.
            **kwargs:
        """
        super(SequenceProcessor, self).__init__(**kwargs)

        self.build_in_vocab = build_in_vocab
        self.min_count = min_count
        self.allow_unk = True
        self.build_vocab_from_labels = build_vocab_from_labels

        if build_in_vocab == 'text':
            self._initial_vocab_dic = {
                self.token_pad: 0,
                self.token_unk: 1,
                self.token_bos: 2,
                self.token_eos: 3
            }
        elif build_in_vocab == 'labeling':
            self._initial_vocab_dic = {
                self.token_pad: 0
            }
        else:
            self._initial_vocab_dic = {}

        self._showed_seq_len_warning = False

    def build_vocab_generator(self,
                              generator: Optional[CorpusGenerator]) -> None:
        if not self.vocab2idx:
            vocab2idx = self._initial_vocab_dic

            token2count: Dict[str, int] = {}

            for sentence, label in tqdm.tqdm(generator, desc="Preparing text vocab dict"):
                if self.build_vocab_from_labels:
                    target = label
                else:
                    target = sentence
                for token in target:
                    count = token2count.get(token, 0)
                    token2count[token] = count + 1

            sorted_token2count = sorted(token2count.items(),
                                        key=operator.itemgetter(1),
                                        reverse=True)
            token2count = collections.OrderedDict(sorted_token2count)

            for token, token_count in token2count.items():
                if token not in vocab2idx and token_count >= self.min_count:
                    vocab2idx[token] = len(vocab2idx)
            self.vocab2idx = vocab2idx
            self.idx2vocab = dict([(v, k) for k, v in self.vocab2idx.items()])

            logging.info("------ Build vocab dict finished, Top 10 token ------")
            for token, index in list(self.vocab2idx.items())[:10]:
                logging.info(f"Token: {token:8s} -> {index}")
            logging.info("------ Build vocab dict finished, Top 10 token ------")

    def transform(self,
                  samples: TextSamplesVar,
                  seq_length: int = None,
                  max_position: int = None,
                  segment: bool = False,
                  **kwargs: Any) -> np.ndarray:
        if seq_length is None:
            seq_length = max([len(i) for i in samples])
            if max_position and seq_length > max_position:
                seq_length = max_position
            if not self._showed_seq_len_warning:
                logging.warning(
                    f'Sequence length is None, will use the max length of the samples, which is {seq_length}')
                self._showed_seq_len_warning = True

        numerized_samples = []
        for seq in samples:
            seq = [self.token_bos] + seq + [self.token_eos]
            if self.allow_unk:
                unk_index = self.vocab2idx[self.token_unk]
                numerized_samples.append([self.vocab2idx.get(token, unk_index) for token in seq])
            else:
                numerized_samples.append([self.vocab2idx[token] for token in seq])

        sample_index = pad_sequences(numerized_samples, seq_length, padding='post', truncating='post')
        token_ids = np.array(sample_index)

        if segment:
            segment_ids = np.zeros(token_ids.shape, dtype=np.int32)
            return token_ids, segment_ids
        else:
            return token_ids

    def inverse_transform(self,  # type: ignore[override]
                          labels: List[List[int]],
                          *,
                          lengths: List[int] = None,
                          **kwargs: Any) -> List[List[str]]:
        result = []
        for index, seq in enumerate(labels):
            labels_ = []
            for idx in seq:
                labels_.append(self.idx2vocab[idx])
            if lengths is not None:
                labels_ = labels_[1:lengths[index]]
            else:
                labels_ = labels_[:-1]
            result.append(labels_)
        return result


if __name__ == "__main__":
    from kashgari.corpus import ChineseDailyNerCorpus
    from kashgari.generators import CorpusGenerator

    logging.basicConfig(level='DEBUG')
    x, y = ChineseDailyNerCorpus.load_data()
    gen = CorpusGenerator(x, y)
    p = SequenceProcessor(vocab_dict_type='labeling')
    p.build_vocab_dict_if_needs(gen)
    print(p.vocab2idx)