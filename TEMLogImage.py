import sys
import os
import pickle
import joblib
import numpy as np
from matplotlib import cm
import matplotlib.path as mpath
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from PIL import Image
from ncempy.io import dm
from matplotlib.lines import Line2D
from matplotlib.artist import Artist
from skimage.measure import profile_line


def dist_point_to_segment(p, s0, s1):
    """
    Get the distance of a point to a segment.

      *p*, *s0*, *s1* are *xy* sequences

    This algorithm from
    http://geomalgorithms.com/a02-_lines.html
    """
    p = np.asarray(p, float)
    s0 = np.asarray(s0, float)
    s1 = np.asarray(s1, float)
    v = s1 - s0
    w = p - s0

    c1 = np.dot(w, v)
    if c1 <= 0:
        return dist(p, s0)

    c2 = np.dot(v, v)
    if c2 <= c1:
        return dist(p, s1)

    b = c1 / c2
    pb = s0 + b * v
    return dist(p, pb)


class PolygonInteractor(object):
    epsilon = 10  # max pixel distance to count as a vertex hit

    def __init__(self, fig, ax, profileax, profileLine, profileLineWidth=1, startPoint=(0, 0), endPoint=(1, 1), pixelScale=1):
        self.ax = ax
        self.fig = fig
        self.profileLine = profileLine
        self.profileax = profileax
        self.pixelScale = pixelScale
        canvas = ax.figure.canvas

        x = [startPoint[0], endPoint[0]]
        y = [startPoint[1], endPoint[1]]
        self.xy = [(x, y) for x, y in zip(x, y)]
        self.line = Line2D(x, y, marker='o', markerfacecolor='r', animated=True)
        self.ax.add_line(self.line)
        self.profileLineWidth = profileLineWidth

        self._ind = None  # the active vertex

        canvas.mpl_connect('draw_event', self.draw_callback)
        canvas.mpl_connect('button_press_event', self.button_press_callback)
        canvas.mpl_connect('button_release_event', self.button_release_callback)
        canvas.mpl_connect('motion_notify_event', self.motion_notify_callback)
        self.canvas = canvas

    # @profile
    def draw_callback(self, event):
        self.ax.draw_artist(self.line)
        self.fig.canvas.flush_events()

    def get_ind_under_point(self, event):
        """get the index of the vertex under point if within epsilon tolerance"""
        # display coords
        xy = np.asarray(self.xy)
        xyt = self.line.get_transform().transform(xy)
        xt, yt = xyt[:, 0], xyt[:, 1]
        d = np.sqrt((xt - event.x)**2 + (yt - event.y)**2)
        indseq = np.nonzero(np.equal(d, np.amin(d)))[0]
        ind = indseq[0]

        if d[ind] >= self.epsilon:
            ind = None

        return ind

    def button_press_callback(self, event):
        """whenever a mouse button is pressed"""
        if event.inaxes is None:
            return
        if event.button != 1:
            return
        self._ind = self.get_ind_under_point(event)

    def button_release_callback(self, event):
        """whenever a mouse button is released"""
        if event.button != 1:
            return
        self._ind = None

    # @profile
    def motion_notify_callback(self, event):
        """on mouse movement"""
        if self._ind is None:
            return
        if event.inaxes is None:
            return
        if event.button != 1:
            return
        x, y = event.xdata, event.ydata
        # print(x, y)
        self.xy[self._ind] = x, y
        self.line.set_data(zip(*self.xy))
        profileLineData = profile_line(plotData, (self.xy[0][1], self.xy[0][0]), (self.xy[1][1], self.xy[1][0]), linewidth=self.profileLineWidth)
        self.profileLine.set_xdata(pixelScale * np.arange(profileLineData.size))
        self.profileLine.set_ydata(profileLineData)
        self.profileax.set_xlim(0, pixelScale*profileLineData.size)
        self.profileax.set_ylim(np.min(profileLineData), np.max(profileLineData))
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()


useCenterDistanceCoords = True  # Assumes center is global max
dmData = dm.dmReader('power removed_ heated to 60C_ SADA 2(1).dm3')
# dmData = dm.dmReader('16 mW_ follows crystal 2_SADA 2(1).dm3')
startPoint = (20, 20)
endPoint = (1000, 2000)
fig, axs = plt.subplots(figsize=(8, 8), nrows=1, ncols=2)
nonlogData = dmData['data']+abs(np.min(dmData['data']))+0.000000000000
plotData = np.log10(nonlogData)
centerX, centerY = np.unravel_index(np.argmax(plotData, axis=None), plotData.shape)
axs[0].imshow(plotData, interpolation='none', origin='lower')
profileLineWidth = 3
profileLineData = profile_line(plotData, startPoint, endPoint, linewidth=profileLineWidth)
offsetStartPoint = (startPoint[0]-centerX, startPoint[1]-centerY)
offsetEndPoint = (endPoint[0]-centerX, endPoint[1]-centerY)
pixelScale = dmData['pixelSize'][0]  # in 1/nm
# if offsetStartPoint[0] > offsetEndPoint[0]:
#     offsetStartPoint, offsetEndPoint = offsetEndPoint, offsetStartPoint

profileLine = axs[1].plot(pixelScale*np.arange(profileLineData.size), profileLineData)[0]
p = PolygonInteractor(fig, axs[0], axs[1], profileLine, profileLineWidth, startPoint, endPoint, pixelScale)
plt.show()
