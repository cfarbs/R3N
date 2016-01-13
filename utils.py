#!/usr/bin/env python
"""Utility functions for MinION signal alignments
"""
from __future__ import print_function
import os
import theano
import sys
import glob
import pandas as pd
import numpy as np
import theano.tensor as T
from itertools import chain
from model import NeuralNetwork, ThreeLayerNetwork, ReLUThreeLayerNetwork
from random import shuffle


def get_motif_range(motifs, kmer_length=6):
    return list(chain(*[range(s, s+kmer_length) for s in motifs]))


def cull_motif_features4(motif, tsv, strand, feature_set=None, kmer_length=6):

    try:
        data = pd.read_table(tsv, usecols=(1, 4, 5, 6, 7, 10, 11, 12),
                             dtype={'ref_pos': np.int32,
                                    'event_idx': np.int32,
                                    'strand': np.str,
                                    'event_mean': np.float64,
                                    'event_noise': np.float64,
                                    'prob': np.float64,
                                    'E_mean': np.float64,
                                    'E_noise': np.float64},
                             header=None,
                             names=['ref_pos', 'strand', 'event_idx', 'event_mean',
                                    'event_noise', 'E_mean', 'E_noise', 'prob']
                             )

        motif_events = get_motif_range(motif, kmer_length=kmer_length)

        if strand in ["t", "c"]:
            motif_rows = data.ix[(data['ref_pos'].isin(motif_events)) & (data['strand'] == strand)]
        else:
            motif_rows = data.ix[(data['ref_pos'].isin(motif_events))]

        if feature_set == "mean":
            features = pd.DataFrame({"ref_pos": motif_rows['ref_pos'],
                                     "delta_mean": motif_rows['event_mean'] - motif_rows['E_mean'],
                                     "strand": motif_rows['strand']}
                                    )

            f = features.sort_values(['ref_pos', 'strand'], ascending=[True, False])\
                .drop_duplicates(subset='delta_mean')
            return f

        elif feature_set == "all":
            features = pd.DataFrame({"ref_pos": motif_rows['ref_pos'],
                                     "delta_mean": motif_rows['event_mean'] - motif_rows['E_mean'],
                                     "delta_noise": motif_rows['event_noise'] - motif_rows['E_noise'],
                                     "posterior": motif_rows['prob'],
                                     "strand": motif_rows['strand']}
                                    )

        elif feature_set == "noise":
            features = pd.DataFrame({"ref_pos": motif_rows['ref_pos'],
                                     "delta_mean": motif_rows['event_mean'] - motif_rows['E_mean'],
                                     "delta_noise": motif_rows['event_noise'] - motif_rows['E_noise'],
                                     "strand": motif_rows['strand']}
                                    )

            f = features.sort_values(['ref_pos', 'strand'], ascending=[True, False])\
                .drop_duplicates(subset='delta_mean')
            return f

        else:
            features = pd.DataFrame({"ref_pos": motif_rows['ref_pos'],
                                     "delta_mean": motif_rows['event_mean'] - motif_rows['E_mean'],
                                     "posterior": motif_rows['prob'],
                                     "strand": motif_rows['strand']}
                                    )

        if features.empty:
            return False

        f = features.sort_values(['ref_pos', 'strand', 'posterior'], ascending=[True, False, False])\
            .drop_duplicates(subset='delta_mean')
        return f

    except:
        return False


def get_nb_features(feature_set):
    assert(feature_set in ['all', 'mean', 'noise', None]), "invalid feature set"
    if feature_set == "mean":
        return 1
    elif feature_set == "noise" or feature_set is None:
        return 2
    else:
        return 3


def collect_data_vectors2(events_per_pos, label, portion, files, strand,
                          motif_starts, dataset_title,
                          max_samples,
                          feature_set=None, kmer_length=6):
    # collect the files
    tsvs = [x for x in glob.glob(files) if os.stat(x).st_size != 0]

    # shuffle
    shuffle(tsvs)

    #assert(portion < 1.0 and max_samples >= 1)

    if max_samples < len(tsvs):
        tsvs = tsvs[:max_samples]

    # get the number of files we're going to use
    split_index = int(portion * len(tsvs))

    # container for training and test data
    # for the echelon alignments, we allow for a defined number of aligned events, there are 6 positions,
    # so for each read (set of observations) we need:
    # (nb_events * nb_event_features * positions) * number_of_strands
    nb_events_per_column = events_per_pos
    nb_event_features = get_nb_features(feature_set)
    nb_positions = 6

    strands = [strand] if strand == "t" or strand == "c" else ["t", "c"]
    nb_strands = len(strands)

    # precompute the size of the vectors
    vector_size = (nb_events_per_column * nb_event_features * nb_positions) * nb_strands
    position_idx_offset = nb_events_per_column * nb_event_features

    # containers
    train_data = []
    tr_append = train_data.append
    xtrain_data = []
    xt_append = xtrain_data.append

    print("{0}: Getting vectors from {1}, collecting {2} features".format(dataset_title, files, nb_event_features),
          end='\n', file=sys.stderr)

    for i, f in enumerate(tsvs):
        # get the dataFrame of all features for all motif positions for this file
        motif_table = cull_motif_features4(motif=motif_starts, tsv=f, feature_set=feature_set,
                                           strand=strand, kmer_length=kmer_length)
        if motif_table is False:
            continue
        for motif_start in motif_starts:
            vect = np.full(shape=vector_size, fill_value=np.nan)
            for idx, position in enumerate(xrange(motif_start, motif_start + nb_positions)):
                # this giant thing takes the DataFrame which has all of the events aligned to the portion we're looking
                # at, gets only the ones aligned to 'position', removes the ref_position column, takes only the highest
                # events_per_pos events, turns it into a list of lists, then chains it into one long list. in case you
                # forgot, the table comes pre-sorted, so when you take the top n events, they are already sorted
                # in descending posterior match prob
                events = []
                for o, s in enumerate(strands):
                    events += list(chain(
                        *motif_table.ix[(motif_table['ref_pos'] == position) & (motif_table['strand'] == s)]
                        .drop(['ref_pos', 'strand'], 1)[:events_per_pos].values.tolist()))
                    # add them to the feature vector
                    for _ in xrange(len(events)):
                        vect[((idx * position_idx_offset) * (o + 1)) + _] = events[_]

            if i < split_index:
                tr_append(vect)
            else:
                xt_append(vect)

    train_labels = np.full(shape=[1, len(train_data)], fill_value=label, dtype=np.int32)
    xtrain_labels = np.full(shape=[1, len(xtrain_data)], fill_value=label, dtype=np.int32)
    return np.asarray(train_data), train_labels, np.asarray(xtrain_data), xtrain_labels


def shuffle_and_maintain_labels(data, labels):
    assert len(data) == len(labels)
    dataset = zip(data, labels)
    shuffle(dataset)
    X = [x[0] for x in dataset]
    y = [x[1] for x in dataset]

    return np.asarray(X), y


def preprocess_data(training_vectors, test_vectors, preprocess=None):
    assert(len(training_vectors.shape) == 2 and len(test_vectors.shape) == 2)
    if preprocess == "center" or preprocess == "normalize":
        training_mean_vector = np.nanmean(training_vectors, axis=0)
        training_vectors -= training_mean_vector
        test_vectors -= training_mean_vector

        if preprocess == "normalize":
            training_std_vector = np.nanstd(training_vectors, axis=0)
            training_vectors /= training_std_vector
            test_vectors /= training_std_vector

    prc_training_vectors = np.nan_to_num(training_vectors)
    prc_test_vectors = np.nan_to_num(test_vectors)

    return prc_training_vectors, prc_test_vectors


def get_network(x, in_dim, n_classes, hidden_dim, type):
    if type == "twoLayer":
        return NeuralNetwork(x=x, in_dim=in_dim, n_classes=n_classes, hidden_dim=hidden_dim)
    if type == "threeLayer":
        return ThreeLayerNetwork(x=x, in_dim=in_dim, n_classes=n_classes, hidden_dim=hidden_dim)
    if type == "ReLUthreeLayer":
        return ReLUThreeLayerNetwork(x=x, in_dim=in_dim, n_classes=n_classes, hidden_dim=hidden_dim)
    else:
        print("Invalid model type", file=sys.stderr)
        return False


def shared_dataset(data_x, data_y, borrow=True):
        """ Function that loads the dataset into shared variables

        The reason we store our dataset in shared variables is to allow
        Theano to copy it into the GPU memory (when code is run on GPU).
        Since copying data into the GPU is slow, copying a minibatch everytime
        is needed (the default behaviour if the data is not in a shared
        variable) would lead to a large decrease in performance.
        """

        shared_x = theano.shared(np.asarray(data_x, dtype=theano.config.floatX),
                                 borrow=borrow)
        shared_y = theano.shared(np.asarray(data_y, dtype=theano.config.floatX),
                                 borrow=borrow)
        # When storing data on the GPU it has to be stored as floats
        # therefore we will store the labels as ``floatX`` as well
        # (``shared_y`` does exactly that). But during our computations
        # we need them as ints (we use labels as index, and if they are
        # floats it doesn't make sense) therefore instead of returning
        # ``shared_y`` we will have to cast it to int. This little hack
        # lets ous get around this issue
        return shared_x, T.cast(shared_y, 'int32')




