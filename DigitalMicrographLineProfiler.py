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
from matplotlib.widgets import Button
from skimage.measure import profile_line
from DigitalMicrographLineProfilerUI import setupOptionsUI


def getNakedNameFromFilePath(name):
    head, tail = os.path.split(name)
    nakedName, fileExtension = os.path.splitext(tail)
    return nakedName


def offsetToOriginalCoords(coords, centerCoord, returnType='tuple'):
    assert returnType.lower() == 'numpy' or returnType.lower() == 'tuple', 'Allowed return types are numpy or tuple'
    if returnType.lower() == 'numpy':
        return np.asarray([coords[0] + centerCoord[0], coords[1] + centerCoord[1]])
    return coords[0] + centerCoord[0], coords[1] + centerCoord[1]


def originalToOffsetCoords(coords, centerCoord, returnType='tuple'):
    assert returnType.lower() == 'numpy' or returnType.lower() == 'tuple', 'Allowed return types are numpy or tuple'
    if returnType.lower() == 'numpy':
        return np.asarray([coords[0] - centerCoord[0], coords[1] - centerCoord[1]])
    return coords[0] - centerCoord[0], coords[1] - centerCoord[1]


def convertLinePointsToCenteredLinePoints(startPoint, centerCoord):
    offsetStartPoint = originalToOffsetCoords(startPoint, centerCoord, 'numpy')
    offsetEndPoint = -offsetStartPoint
    # if offsetStartPoint[0] > offsetEndPoint[0]:
    #     offsetStartPoint, offsetEndPoint = offsetEndPoint, offsetStartPoint
    startPoint = offsetToOriginalCoords(offsetStartPoint, centerCoord)
    endPoint = offsetToOriginalCoords(offsetEndPoint, centerCoord)
    return startPoint, endPoint


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

    def __init__(self, fig, ax, profileax, plotData, startPoint=(0, 0), endPoint=(1, 1), pixelScale=1, centerCoord=(0, 0), setupOptions=None):
        assert setupOptions is not None, "You must supply a SetupOptions object"
        self.ax = ax
        self.fig = fig
        self.profileax = profileax
        self.pixelScale = pixelScale
        self.useCenteredLine = setupOptions.useCenteredLine
        self.centerCoord = centerCoord
        self.fileName = setupOptions.imageFilePath
        self.plotData = plotData
        self.useLogData = setupOptions.useLogData

        if self.useCenteredLine:
            _, endPoint = convertLinePointsToCenteredLinePoints(startPoint, self.centerCoord)

        self.xy = [startPoint, endPoint]
        self.line = Line2D(list(zip(*self.xy))[0], list(zip(*self.xy))[1], marker='o', markerfacecolor='r', animated=True)
        self.ax.add_line(self.line)
        self.profileLineWidth = setupOptions.profileLineWidth
        self.profileLineData = profile_line(self.plotData, (self.xy[0][1], self.xy[0][0]), (self.xy[1][1], self.xy[1][0]), linewidth=self.profileLineWidth)

        if self.useCenteredLine:
            self.xData = self.pixelScale * (np.arange(self.profileLineData.size) - self.profileLineData.size/2)
        else:
            self.xData = self.pixelScale * np.arange(self.profileLineData.size)
        self.profileLine = axs[1].plot(self.xData, self.profileLineData)[0]
        self.profileax.autoscale(enable=True, axis='x', tight=True)
        self.profileax.autoscale(enable=True, axis='y', tight=True)

        self._ind = None  # the active vertex
        self.ax.figure.canvas.mpl_connect('draw_event', self.draw_callback)
        self.ax.figure.canvas.mpl_connect('button_press_event', self.button_press_callback)
        self.ax.figure.canvas.mpl_connect('button_release_event', self.button_release_callback)
        self.ax.figure.canvas.mpl_connect('motion_notify_event', self.motion_notify_callback)

    def draw_callback(self, event):
        self.ax.draw_artist(self.line)
        self.fig.canvas.flush_events()

    def exportData(self, event):
        with open(getNakedNameFromFilePath(self.fileName) + '.txt', 'w') as file:
            if self.useLogData:
                file.write('%s\t%s\n' % ('Reciprocal Distance (1/nm)', 'Log(Intensity)'))
            else:
                file.write('%s\t%s\n' % ('Reciprocal Distance (1/nm)', 'Intensity'))
            for reciprocalDistance, intensity in zip(self.xData, self.profileLineData):
                file.write('%s\t%s\n' % (str(reciprocalDistance), str(intensity)))

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

        if self.useCenteredLine:
            _, otherPoint = convertLinePointsToCenteredLinePoints((x, y), self.centerCoord)
            if self._ind == 0:
                self.xy[1] = otherPoint
            else:
                self.xy[0] = otherPoint

        self.line.set_data(zip(*self.xy))
        self.profileLineData = profile_line(self.plotData, (self.xy[0][1], self.xy[0][0]), (self.xy[1][1], self.xy[1][0]), linewidth=self.profileLineWidth)

        if self.useCenteredLine:
            xDataLims = (-self.pixelScale*self.profileLineData.size/2, self.pixelScale*self.profileLineData.size/2)
            self.xData = self.pixelScale * (np.arange(self.profileLineData.size) - self.profileLineData.size/2)
        else:
            xDataLims = (0, self.pixelScale*self.profileLineData.size)
            self.xData = self.pixelScale * np.arange(self.profileLineData.size)
        self.profileLine.set_xdata(self.xData)
        self.profileLine.set_ydata(self.profileLineData)
        self.profileax.set_xlim(xDataLims)
        self.profileax.set_ylim(np.min(self.profileLineData), np.max(self.profileLineData))
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()


setupOptions = setupOptionsUI()
dmData = dm.dmReader(setupOptions.imageFilePath)
startPoint = (20, 20)
endPoint = (1000, 2000)
fig, axs = plt.subplots(figsize=(8, 8), nrows=1, ncols=2)
fig.canvas.set_window_title(getNakedNameFromFilePath(setupOptions.imageFilePath))
axs[1].set_xlabel('Reciprocal Distance (1/nm)')
if setupOptions.useLogData:
    axs[1].set_ylabel('Log(Intensity)')
else:
    axs[1].set_ylabel('Intensity')

nonlogData = dmData['data']+abs(np.min(dmData['data']))
if setupOptions.useLogData:
    plotData = np.log10(nonlogData)
else:
    plotData = nonlogData
centerRow, centerCol = np.unravel_index(np.argmax(plotData, axis=None), plotData.shape)
centerCoord = (centerCol, centerRow)
axs[0].imshow(plotData, interpolation='none', origin='lower')

pixelScale = dmData['pixelSize'][0]  # in 1/nm
p = PolygonInteractor(fig, axs[0], axs[1], plotData, startPoint, endPoint, pixelScale, centerCoord, setupOptions)
plt.subplots_adjust(bottom=0.15)
axExport = plt.axes([0.75, 0.02, 0.15, 0.05])
bExport = Button(axExport, 'Export Data')
bExport.on_clicked(p.exportData)
plt.show()
