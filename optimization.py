#!/usr/bin/env python
from __future__ import print_function
import os, sys
import cPickle
import theano
import theano.tensor as T
import numpy as np
from utils import shared_dataset, get_network


def mini_batch_sgd(motif, train_data, labels, xTrain_data, xTrain_targets,
                   learning_rate, L1_reg, L2_reg, epochs,
                   batch_size,
                   hidden_dim, model_type, model_file=None,
                   trained_model_dir=None, verbose=True, extra_args=None
                   ):
    # Preamble #
    # determine dimensionality of data and number of classes
    n_train_samples, data_dim = train_data.shape
    n_classes = len(set(labels))

    # compute number of mini-batches for training, validation and testing
    train_set_x, train_set_y = shared_dataset(train_data, labels, True)
    xtrain_set_x, xtrain_set_y = shared_dataset(xTrain_data, xTrain_targets, True)
    n_train_batches = train_set_x.get_value(borrow=True).shape[0] / batch_size
    n_xtrain_batches = xtrain_set_x.get_value(borrow=True).shape[0] / batch_size

    batch_index = T.lscalar()

    # containers to hold mini-batches
    x = T.matrix('x')
    y = T.ivector('y')

    net = get_network(x=x, in_dim=data_dim, n_classes=n_classes, hidden_dim=hidden_dim, model_type=model_type,
                      extra_args=extra_args)

    if net is False:
        return False

    # cost function
    cost = (net.negative_log_likelihood(labels=y) + L1_reg * net.L1 + (L2_reg / n_train_samples) * net.L2_sq)

    xtrain_fcn = theano.function(inputs=[batch_index],
                                 outputs=net.errors(y),
                                 givens={
                                     x: xtrain_set_x[batch_index * batch_size: (batch_index + 1) * batch_size],
                                     y: xtrain_set_y[batch_index * batch_size: (batch_index + 1) * batch_size]
                                 })

    # gradients
    nambla_params = [T.grad(cost, param) for param in net.params]

    # update tuple
    updates = [(param, param - learning_rate * nambla_param)
               for param, nambla_param in zip(net.params, nambla_params)]

    # main function? could make this an attribute and reduce redundant code
    train_fcn = theano.function(inputs=[batch_index],
                                outputs=cost,
                                updates=updates,
                                givens={
                                    x: train_set_x[batch_index * batch_size: (batch_index + 1) * batch_size],
                                    y: train_set_y[batch_index * batch_size: (batch_index + 1) * batch_size]
                                })

    train_error_fcn = theano.function(inputs=[batch_index],
                                      outputs=net.errors(y),
                                      givens={
                                          x: train_set_x[batch_index * batch_size: (batch_index + 1) * batch_size],
                                          y: train_set_y[batch_index * batch_size: (batch_index + 1) * batch_size]
                                      })

    if model_file is not None:
        net.load(model_file)

    # do the actual training
    batch_costs = [np.inf]
    add_to_batch_costs = batch_costs.append
    xtrain_accuracies = []
    add_to_xtrain_acc = xtrain_accuracies.append
    train_accuracies = []
    add_to_train_acc = train_accuracies.append
    xtrain_costs_bin = []

    best_xtrain_accuracy = -np.inf
    best_model = ''

    check_frequency = int(epochs / 10)

    for epoch in xrange(0, epochs):
        if epoch % check_frequency == 0:
            # get the accuracy on the cross-train data
            xtrain_errors = [xtrain_fcn(_) for _ in xrange(n_xtrain_batches)]
            avg_xtrain_errors = np.mean(xtrain_errors)
            avg_xtrain_accuracy = 100 * (1 - avg_xtrain_errors)
            # then the training set
            train_errors = [train_error_fcn(_) for _ in xrange(n_train_batches)]
            avg_training_errors = np.mean(train_errors)
            avg_train_accuracy = 100 * (1 - avg_training_errors)
            # collect for tracking progress
            add_to_xtrain_acc(avg_xtrain_accuracy)
            add_to_train_acc(avg_train_accuracy)
            xtrain_costs_bin += xtrain_errors

            if verbose:
                print("{0}: epoch {1}, batch cost {2}, train accuracy {3}, cross-train accuracy {4}"
                      .format(motif, epoch, batch_costs[-1], avg_train_accuracy, avg_xtrain_accuracy), file=sys.stderr)

            # if we're getting better, save the model, the 'oldest' model should be the one with the highest
            # cross-train accuracy
            if avg_xtrain_accuracy >= best_xtrain_accuracy and trained_model_dir is not None:
                if not os.path.exists(trained_model_dir):
                    os.makedirs(trained_model_dir)
                # update the best accuracy and best model
                best_xtrain_accuracy = avg_xtrain_accuracy
                best_model = "{0}model{1}.pkl".format(trained_model_dir, epoch)
                net.write(best_model)

        for i in xrange(n_train_batches):
            batch_avg_cost = train_fcn(i)
            try:
                if i % (n_train_batches / 10) == 0:
                    add_to_batch_costs(float(batch_avg_cost))
            except ZeroDivisionError:
                pass

    # pickle the summary stats for the training
    summary = {
        "batch_costs": batch_costs,
        "xtrain_accuracies": xtrain_accuracies,
        "train_accuracies": train_accuracies,
        "xtrain_errors": xtrain_costs_bin,
        "best_model": best_model
    }
    if trained_model_dir is not None:
        with open("{}summary_stats.pkl".format(trained_model_dir), 'w') as f:
            cPickle.dump(summary, f)

    return net, summary


def mini_batch_sgd_with_annealing(motif, train_data, labels, xTrain_data, xTrain_targets,
                                  learning_rate, L1_reg, L2_reg, epochs,
                                  batch_size,
                                  hidden_dim, model_type, model_file=None,
                                  trained_model_dir=None, verbose=True, extra_args=None):
    # Preamble #
    # determine dimensionality of data and number of classes
    n_train_samples, data_dim = train_data.shape
    n_classes = len(set(labels))

    # compute number of mini-batches for training, validation and testing
    train_set_x, train_set_y = shared_dataset(train_data, labels, True)
    xtrain_set_x, xtrain_set_y = shared_dataset(xTrain_data, xTrain_targets, True)
    n_train_batches = train_set_x.get_value(borrow=True).shape[0] / batch_size
    n_xtrain_batches = xtrain_set_x.get_value(borrow=True).shape[0] / batch_size

    batch_index = T.lscalar()

    # containers to hold mini-batches
    x = T.matrix('x')
    y = T.ivector('y')

    net = get_network(x=x, in_dim=data_dim, n_classes=n_classes, hidden_dim=hidden_dim, model_type=model_type,
                      extra_args=extra_args)

    if net is False:
        return False

    # cost function
    cost = (net.negative_log_likelihood(labels=y) + L1_reg * net.L1 + (L2_reg / n_train_samples) * net.L2_sq)

    xtrain_fcn = theano.function(inputs=[batch_index],
                                 outputs=net.errors(y),
                                 givens={
                                     x: xtrain_set_x[batch_index * batch_size: (batch_index + 1) * batch_size],
                                     y: xtrain_set_y[batch_index * batch_size: (batch_index + 1) * batch_size]
                                 })

    # gradients
    nambla_params = [T.grad(cost, param) for param in net.params]

    # update tuple
    dynamic_learning_rate = T.as_tensor_variable(learning_rate)

    # dynamic_learning_rate = learning_rate
    updates = [(param, param - dynamic_learning_rate * nambla_param)
               for param, nambla_param in zip(net.params, nambla_params)]

    # main function? could make this an attribute and reduce redundant code
    train_fcn = theano.function(inputs=[batch_index],
                                outputs=cost,
                                updates=updates,
                                givens={
                                    x: train_set_x[batch_index * batch_size: (batch_index + 1) * batch_size],
                                    y: train_set_y[batch_index * batch_size: (batch_index + 1) * batch_size]
                                })
    train_error_fcn = theano.function(inputs=[batch_index],
                                      outputs=net.errors(y),
                                      givens={
                                          x: train_set_x[batch_index * batch_size: (batch_index + 1) * batch_size],
                                          y: train_set_y[batch_index * batch_size: (batch_index + 1) * batch_size]
                                      })

    if model_file is not None:
        net.load(model_file)

    # do the actual training
    batch_costs = [np.inf]
    add_to_batch_costs = batch_costs.append
    xtrain_accuracies = []
    add_to_xtrain_acc = xtrain_accuracies.append
    train_accuracies = []
    add_to_train_acc = train_accuracies.append
    xtrain_costs_bin = []
    prev_xtrain_cost = 1e-10

    best_xtrain_accuracy = -np.inf
    best_model = ''
    check_frequency = int(epochs / 10)

    for epoch in xrange(0, epochs):
        # evaluation of training progress and summary stat collection
        if epoch % check_frequency == 0:
            # get the accuracy on the cross-train data
            xtrain_errors = [xtrain_fcn(_) for _ in xrange(n_xtrain_batches)]
            avg_xtrain_errors = np.mean(xtrain_errors)
            avg_xtrain_accuracy = 100 * (1 - avg_xtrain_errors)
            # then the training set
            train_errors = [train_error_fcn(_) for _ in xrange(n_train_batches)]
            avg_training_errors = np.mean(train_errors)
            avg_train_accuracy = 100 * (1 - avg_training_errors)
            # collect for tracking progress
            add_to_xtrain_acc(avg_xtrain_accuracy)
            add_to_train_acc(avg_train_accuracy)
            xtrain_costs_bin += xtrain_errors

            if verbose:
                print("{0}: epoch {1}, batch cost {2}, train accuracy {3}, cross-train accuracy {4}"
                      .format(motif, epoch, batch_costs[-1], avg_train_accuracy, avg_xtrain_accuracy), file=sys.stderr)

            # if we're getting better, save the model, the 'oldest' model should be the one with the highest
            # cross-train accuracy
            if avg_xtrain_accuracy >= best_xtrain_accuracy and trained_model_dir is not None:
                if not os.path.exists(trained_model_dir):
                    os.makedirs(trained_model_dir)
                # update the best accuracy and best model
                best_xtrain_accuracy = avg_xtrain_accuracy
                best_model = "{0}model{1}.pkl".format(trained_model_dir, epoch)
                net.write(best_model)

        for i in xrange(n_train_batches):
            batch_avg_cost = train_fcn(i)
            if i % (n_train_batches / 10) == 0:
                add_to_batch_costs(float(batch_avg_cost))

        # annealing protocol
        mean_xtrain_cost = np.mean([xtrain_fcn(_) for _ in xrange(n_xtrain_batches)])
        if mean_xtrain_cost / prev_xtrain_cost < 1.0:
            dynamic_learning_rate *= 0.9

        if mean_xtrain_cost > prev_xtrain_cost:
            dynamic_learning_rate *= 1.05
        prev_xtrain_cost = mean_xtrain_cost

    # pickle the summary stats for the training
    summary = {
        "batch_costs": batch_costs,
        "xtrain_accuracies": xtrain_accuracies,
        "train_accuracies": train_accuracies,
        "xtrain_errors": xtrain_costs_bin,
        "best_model": best_model
    }
    if trained_model_dir is not None:
        with open("{}summary_stats.pkl".format(trained_model_dir), 'w') as f:
            cPickle.dump(summary, f)

    return net, summary
