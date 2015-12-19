#!/usr/bin/env python

from toy_datasets import *
from neural_network import *
from utils import *
from activation_functions import *







# generating test data
#X, Y = generate_2_class_moon_data()
#X2, Y2 = generate_2_class_moon_data()
#X, Y = generate_3_class_spiral_data(nb_classes=3, theta=0.5, plot=False)
#X2, Y2 = generate_3_class_spiral_data(nb_classes=3, theta=0.5, plot=False)
#X, y = load_iris_dataset()

# digit dataset
#train, test = load_digit_dataset(500, 0.1)
#X = np.array([x[0] for x in train])
#Y = [y[1] for y in train]
#X2 = np.array([x[0] for x in test])
#Y2 = [y[1] for y in test]


# running demo models
#m = build_model2(X, y, 3, 50)
#m = build_model1(train_data=X, labels=y, nb_classes=10, nn_hdim=50, print_loss=True)
#plot_decision_boundary(lambda x: predict(m, x), X, y)

# testing library

#net = NeuralNetwork([2, 10, 2], hyperbolic_tangent)

#net = NeuralNetwork(input_dim=X.shape[1],
#                    nb_classes=len(set(Y)),
#                    hidden_dims=[100],
#                    activation_function=hyperbolic_tangent)

#net.mini_batch_sgd(training_data=X,
#                   labels=Y,
#                   epochs=5000,
#                   batch_size=10,
#                   epsilon=0.001,
#                   lbda=0.001)


#net.fit(X, Y, epochs=5000, epsilon=0.001, lbda=0.001, print_loss=True)
#t = net.evaluate(X2, Y2)
#print net.predict_old(X2)[1:10]
#print net.predict(X2)[1:10]
#print net.predict_old(X2)[1:10] == net.predict(X2)[1:10]
#plot_decision_boundary(lambda x: np.argmax(net.predict(x), axis=1),
#                       X, Y)

labels = []
c = "../marginAlign/cPecan/tests/test_alignments/c100/tempFiles_alignment/"
train, labels, test = collect_data_vectors(c, True, labels, 0, 0.4, 747, 100)
train1, labels, test1 = collect_data_vectors(c, True, labels, 0, 0.4, 747, 100)
t = np.vstack((train, train1, test1))
print np.nan_to_num(t)
#center_features_on_training_data(train, test)

