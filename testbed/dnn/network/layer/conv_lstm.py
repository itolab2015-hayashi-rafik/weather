# -*- coding: utf-8 -*-
import numpy
import theano
import theano.tensor as T
from theano.tensor.signal import downsample

from conv import conv2d_keepshape
from rnn import RNN


class ConvLSTM(RNN):
    """
    LSTM
    see: http://deeplearning.net/tutorial/lstm.html
    see: https://github.com/JonathanRaiman/theano_lstm/blob/master/theano_lstm/__init__.py
    """
    def __init__(self, input_shape, filter_shape, has_input=True, activation=T.tanh, clip_gradients=False, prefix="ConvLSTM", **kwargs):
        '''
         initialize ConvLSTM

         :type input_shape: tuple or list of length 3
         :param input_shape: (num input feature maps,
                              image height, image width)

         :type filter_shape: tuple or list of length 4
         :param filter_shape: (number of filters, num input feature maps,
                               filter height, filter width)

         :param activation:
         :param clip_gradients:
         :param prefix:
         :param kwargs:
         :return:
         '''
        # assert that the number of input feature maps equals to the number of feature maps in filter_shape
        assert(input_shape[0] == filter_shape[1])

        self.input_shape = input_shape
        self.input_filter_shape = filter_shape
        self.hidden_filter_shape = (filter_shape[0], filter_shape[0], filter_shape[2], filter_shape[3])
        self.output_shape = (filter_shape[0], input_shape[1], input_shape[2])
        self.has_input = has_input

        # ConvLSTM receives in total:
        # "num of input feature maps * input height * input width" inputs
        n_in = numpy.prod(self.input_shape)

        # ConvLSTM outputs in total:
        # "num of output feature maps * output height * output width" outputs
        # FIXME: consider downsampling, using poolsize
        n_out = numpy.prod(self.output_shape)

        super(ConvLSTM, self).__init__(n_in, n_out, activation=activation, clip_gradients=clip_gradients, prefix=prefix, **kwargs)

    def conv_x(self, input, filters):
        # apply convolution for input-hidden connection
        return self.conv(
            input=input,
            filters=filters,
            image_shape=(None, self.input_shape[0], self.input_shape[1], self.input_shape[2]),
            filter_shape=self.input_filter_shape
        )

    def conv_h(self, input, filters):
        # apply convolution for hidden-hidden connection
        return self.conv(
            input=input,
            filters=filters,
            image_shape=(None, self.output_shape[0], self.output_shape[1], self.output_shape[2]),
            filter_shape=self.hidden_filter_shape
        )

    def conv(self, input, filters, image_shape, filter_shape):
        # convolve input feature maps with filters
        x = conv2d_keepshape(
            input=input,
            filters=filters,
            image_shape=image_shape,
            filter_shape=filter_shape
        )

        return x

    def setup(self):
        # initialize weights
        if self.has_input:
            Wxf_value = self.random_initialization(self.input_filter_shape)
            self.Wxf = self._shared(Wxf_value, name="Wxf", borrow=True)
            Wxi_value = self.random_initialization(self.input_filter_shape)
            self.Wxi = self._shared(Wxi_value, name="Wxi", borrow=True)
            Wxc_value = self.random_initialization(self.input_filter_shape)
            self.Wxc = self._shared(Wxc_value, name="Wxc", borrow=True)
            Wxo_value = self.random_initialization(self.input_filter_shape)
            self.Wxo = self._shared(Wxo_value, name="Wxo", borrow=True)

        Whf_value = self.random_initialization(self.hidden_filter_shape)
        self.Whf = self._shared(Whf_value, name="Whf", borrow=True)
        Whi_value = self.random_initialization(self.hidden_filter_shape)
        self.Whi = self._shared(Whi_value, name="Whi", borrow=True)
        Whc_value = self.random_initialization(self.hidden_filter_shape)
        self.Whc = self._shared(Whc_value, name="Whc", borrow=True)
        Who_value = self.random_initialization(self.hidden_filter_shape)
        self.Who = self._shared(Who_value, name="Who", borrow=True)

        Wcf_value = self.zeros((self.output_shape[0],))
        self.Wcf = self._shared(Wcf_value, name="Wcf", borrow=True)
        Wci_value = self.zeros((self.output_shape[0],))
        self.Wci = self._shared(Wci_value, name="Wci", borrow=True)
        Wco_value = self.zeros((self.output_shape[0],))
        self.Wco = self._shared(Wco_value, name="Wco", borrow=True)

        bf_value = self.zeros((self.output_shape[0],))
        self.bf = self._shared(bf_value, name="bf", borrow=True)
        bi_value = self.zeros((self.output_shape[0],))
        self.bi = self._shared(bi_value, name="bi", borrow=True)
        bc_value = self.zeros((self.output_shape[0],))
        self.bc = self._shared(bc_value, name="bc", borrow=True)
        bo_value = self.zeros((self.output_shape[0],))
        self.bo = self._shared(bo_value, name="bo", borrow=True)

    def step(self, m, x, c_, h_):
        # assume x is of shape (n_samples, num of input feature maps, input height, input width),
        # c_ is of shape (n_samples, num of hidden feature maps, output height, output width),
        # h_ is of shape (n_samples, num of output feature maps, output height, output width).
        # Note num of hidden feature maps = num of output feature maps,
        # input height = output height, and input width = output width

        if self.has_input:
            f = T.nnet.sigmoid(self.conv_x(x, self.Wxf)
                               + self.conv_h(h_, self.Whf)
                               + c_ * self.Wcf.dimshuffle('x',0,'x','x')
                               + self.bf.dimshuffle('x',0,'x','x'))
            i = T.nnet.sigmoid(self.conv_x(x, self.Wxi)
                               + self.conv_h(h_, self.Whi)
                               + c_ * self.Wci.dimshuffle('x',0,'x','x')
                               + self.bi.dimshuffle('x',0,'x','x'))
            c = self.activation(self.conv_x(x, self.Wxc)
                                + self.conv_h(h_, self.Whc)
                                + self.bc.dimshuffle('x',0,'x','x'))
            c = f * c_ + i * c

            o = T.nnet.sigmoid(self.conv_x(x, self.Wxo)
                               + self.conv_h(h_, self.Who)
                               + c  * self.Wco.dimshuffle('x',0,'x','x')
                               + self.bo.dimshuffle('x',0,'x','x'))
            h = o * self.activation(c)
        else:
            f = T.nnet.sigmoid(self.conv_h(h_, self.Whf)
                               + c_ * self.Wcf.dimshuffle('x',0,'x','x')
                               + self.bf.dimshuffle('x',0,'x','x'))
            i = T.nnet.sigmoid(self.conv_h(h_, self.Whi)
                               + c_ * self.Wci.dimshuffle('x',0,'x','x')
                               + self.bi.dimshuffle('x',0,'x','x'))
            c = self.activation(self.conv_h(h_, self.Whc)
                                + self.bc.dimshuffle('x',0,'x','x'))
            c = f * c_ + i * c

            o = T.nnet.sigmoid(self.conv_h(h_, self.Who)
                               + c  * self.Wco.dimshuffle('x',0,'x','x')
                               + self.bo.dimshuffle('x',0,'x','x'))
            h = o * self.activation(c)

        return c, h

    def outputs_info(self, n_samples):
        # initialize hidden states: c, h
        shape = (n_samples,) + self.output_shape
        return [
            T.unbroadcast(T.alloc(numpy.asarray(0., dtype=theano.config.floatX), *shape), *range(len(shape))), # c
            T.unbroadcast(T.alloc(numpy.asarray(0., dtype=theano.config.floatX), *shape), *range(len(shape)))  # h
        ]

    @property
    def params(self):
        if self.has_input:
            return [self.Wxf, self.Whf, self.Wcf, self.bf,
                    self.Wxi, self.Whi, self.Wci, self.bi,
                    self.Wxc, self.Whc, self.bc,
                    self.Wxo, self.Who, self.Wco, self.bo]
        else:
            return [self.Whf, self.Wcf, self.bf,
                    self.Whi, self.Wci, self.bi,
                    self.Whc, self.bc,
                    self.Who, self.Wco, self.bo]

    @params.setter
    def params(self, param_list):
        if self.has_input:
            self.Wxf.set_value(param_list[0].get_value())
            self.Whf.set_value(param_list[1].get_value())
            self.Wcf.set_value(param_list[2].get_value())
            self.bf.set_value(param_list[3].get_value())
            self.Wxi.set_value(param_list[4].get_value())
            self.Whi.set_value(param_list[5].get_value())
            self.Wci.set_value(param_list[6].get_value())
            self.bi.set_value(param_list[7].get_value())
            self.Wxc.set_value(param_list[8].get_value())
            self.Whc.set_value(param_list[9].get_value())
            self.bc.set_value(param_list[10].get_value())
            self.Wxo.set_value(param_list[11].get_value())
            self.Who.set_value(param_list[12].get_value())
            self.Wco.set_value(param_list[13].get_value())
            self.bo.set_value(param_list[14].get_value())
        else:
            self.Whf.set_value(param_list[1].get_value())
            self.Wcf.set_value(param_list[2].get_value())
            self.bf.set_value(param_list[3].get_value())
            self.Whi.set_value(param_list[4].get_value())
            self.Wci.set_value(param_list[5].get_value())
            self.bi.set_value(param_list[6].get_value())
            self.Whc.set_value(param_list[7].get_value())
            self.bc.set_value(param_list[8].get_value())
            self.Who.set_value(param_list[9].get_value())
            self.Wco.set_value(param_list[10].get_value())
            self.bo.set_value(param_list[11].get_value())


