#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A class for getting numeric or categorical ratings, e.g., a 1-to-7 scale."""

# Part of the PsychoPy library
# Copyright (C) 2015 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

from __future__ import absolute_import, division, print_function

import copy
import numpy as np

from psychopy import core, logging, event
from .basevisual import MinimalStim, ColorMixin, BaseVisualStim
from .rect import Rect
from .grating import GratingStim
from .elementarray import ElementArrayStim
from .circle import Circle
from .shape import ShapeStim
from .text import TextStim
from ..tools.attributetools import logAttrib, setAttribute, attributeSetter
from ..constants import FINISHED, STARTED, NOT_STARTED



class Slider(MinimalStim, ColorMixin):
    """A class for obtaining ratings, e.g., on a 1-to-7 or categorical scale.

    A simpler alternative to RatingScale, to be customised with code rather
    than with arguments.

    A RatingScale instance is a re-usable visual object having a ``draw()``
    method, with customizable appearance and response options. ``draw()``
    displays the rating scale, handles the subject's mouse or key responses,
    and updates the display. When the subject accepts a selection,
    ``.noResponse`` goes ``False`` (i.e., there is a response).

    You can call the ``getRating()`` method anytime to get a rating,
    ``getRT()`` to get the decision time, or ``getHistory()`` to obtain
    the entire set of (rating, RT) pairs.

    For other examples see Coder Demos -> stimuli -> ratingsNew.py.

    :Authors:
        - 2018: Jon Peirce
    """

    def __init__(self,
                 win,
                 ticks=(1, 2, 3, 4, 5),
                 labels=None,
                 startValue=None,
                 pos=None,
                 size=None,
                 units=None,
                 flip=False,
                 style='rating', styleTweaks=[],
                 granularity=0,
                 readOnly=False,
                 color='White',
                 fillColor='Red',
                 borderColor='White',
                 colorSpace='rgb',
                 opacity=None,
                 font='Helvetica Bold',
                 depth=0,
                 name=None,
                 labelHeight=None,
                 labelWrapWidth=None,
                 autoDraw=False,
                 autoLog=True):
        """

        Parameters
        ----------
        win : psychopy.visual.Window
            Into which the scale will be rendered

        ticks : list or tuple
            A set of values for tick locations. If given a list of numbers then
            these determine the locations of the ticks (the first and last
            determine the endpoints and the rest are spaced according to
            their values between these endpoints.

        labels : a list or tuple
            The text to go with each tick (or spaced evenly across the ticks).
            If you give 3 labels but 5 tick locations then the end and middle
            ticks will be given labels. If the labels can't be distributed
            across the ticks then an error will be raised. If you want an
            uneven distribution you should include a list matching the length
            of ticks but with some values set to None

        pos : XY pair (tuple, array or list)

        size : w,h pair (tuple, array or list)
            The size for the scale defines the area taken up by the line and
            the ticks.
            This also controls whether the scale is horizontal or vertical.

        units : the units to interpret the pos and size

        flip : bool
            By default the labels will be below or left of the line. This
            puts them above (or right)

        granularity : int or float
            The smallest valid increments for the scale. 0 gives a continuous
            (e.g. "VAS") scale. 1 gives a traditional likert scale. Something
            like 0.1 gives a limited fine-grained scale.

        color :
            Color of the line/ticks/labels according to the color space

        font : font name

        autodraw :

        depth :

        name :

        autoLog :
        """
        # what local vars are defined (these are the init params) for use by
        # __repr__
        self._initParams = dir()
        super(Slider, self).__init__(name=name, autoLog=False)

        self.win = win
        self.ticks = np.asarray(ticks)
        self.labels = labels

        if pos is None:
            self.__dict__['pos'] = (0, 0)
        else:
            self.__dict__['pos'] = pos

        if units is None:
            self.units = win.units
        else:
            self.units = units

        if size is None:
            defaultSizes = {
                None: [self.win.size[0]*1.0, self.win.size[1]*0.1],
                'height': [1.0, 0.1],
                'norm': [1.0, 0.1],
                'deg': [3.14, 0.314],
                'cm': [10, 1],
                'pix': [self.win.size[0]*1.0, self.win.size[1]*0.1]
            }
            self._size = defaultSizes[self.units]
        else:
            self._size = size

        self.flip = flip
        self.granularity = granularity
        self.colorSpace = colorSpace
        self.color = color
        self.fillColor = fillColor
        self.borderColor = borderColor
        self.opacity = opacity
        self.font = font
        self.autoDraw = autoDraw
        self.depth = depth
        self.name = name
        self.autoLog = autoLog
        self.readOnly = readOnly

        self.categorical = False  # will become True if no ticks set only labels
        self.startValue = self.rating =  self.markerPos = startValue
        self.rt = None
        self.history = []
        self.marker = None
        self.line = None
        self.tickLines = []
        self.tickLocs = None
        self.labelLocs = None
        self.labelWrapWidth = labelWrapWidth
        self.labelHeight = labelHeight or min(self._size)
        self._lineAspectRatio = 0.01
        self._updateMarkerPos = True
        self._dragging = False
        self.mouse = event.Mouse(win=win)
        self._mouseStateClick = None  # so we can rule out long click probs
        self._mouseStateXY = None  # so we can rule out long click probs

        self.validArea = None
        self._createElements()
        # some things must wait until elements created
        self.contrast = 1.0

        # set autoLog (now that params have been initialised)
        self.autoLog = autoLog
        if autoLog:
            logging.exp("Created %s = %s" % (self.name, repr(self)))
        self.status = NOT_STARTED
        self.responseClock = core.Clock()

        # set the style when everything else is set
        self.styleTweaks = []
        self.style = style
        self.styleTweaks += styleTweaks

    def __repr__(self, complete=False):
        return self.__str__(complete=complete)  # from MinimalStim

    @property
    def _lineL(self):
        """The length of the line (in the size units)
        """
        return max(self.size)

    @property
    def _tickL(self):
        """The length of the line (in the size units)
        """
        return min(self.size)

    @property
    def _lineW(self):
        """The length of the line (in the size units)
        """
        return max(self.size) * self._lineAspectRatio

    @property
    def horiz(self):
        """(readonly) determines from self.size whether the scale is horizontal"""
        return self.size[0] > self.size[1]

    @property
    def size(self):
        """The size for the scale defines the area taken up by the line and
            the ticks.
        """
        return self._size

    @property
    def opacity(self):
        BaseVisualStim.opacity.fget(self)
    @opacity.setter
    def opacity(self, value):
        BaseVisualStim.opacity.fset(self, value)
        self.fillColor = self._fillColor.copy()
        self.borderColor = self._borderColor.copy()
        self.foreColor = self._foreColor.copy()
    def setOpacity(self, value):
        self.opacity = value

    @property
    def foreColor(self):
        ColorMixin.foreColor.fget(self)
    @foreColor.setter
    def foreColor(self, value):
        ColorMixin.foreColor.fset(self, value)
        # Set color of each label
        if hasattr(self, 'labelObjs'):
            for lbl in self.labelObjs:
                lbl.color = self._foreColor.copy()

    @property
    def fillColor(self):
        ColorMixin.fillColor.fget(self)
    @fillColor.setter
    def fillColor(self, value):
        ColorMixin.fillColor.fset(self, value)
        # Set color of marker
        if hasattr(self, 'marker'):
            self.marker.fillColor = self._foreColor.copy()

    @property
    def borderColor(self):
        ColorMixin.borderColor.fget(self)
    @borderColor.setter
    def borderColor(self, value):
        ColorMixin.borderColor.fset(self, value)
        # Set color of lines
        if hasattr(self, 'line'):
            if self.style not in ["scrollbar"]: # Scrollbar doesn't have an outline
                self.line.color = self._borderColor.copy()
            self.line.fillColor = self._borderColor.copy()
            if self.style in ["slider", "scrollbar"]: # Slider and scrollbar need translucent fills
                self.line._fillColor.alpha *= 0.2
        if hasattr(self, 'tickLines'):
            self.tickLines.colors = self._borderColor.copy()
            self.tickLines.opacities = self._borderColor.alpha


    def reset(self):
        """Resets the slider to its starting state (so that it can be restarted
        on each trial with a new stimulus)
        """
        self.markerPos = self.rating = self.startValue
        self.history = []
        self.rt = None
        self.responseClock.reset()
        self.status = NOT_STARTED

    def _createElements(self):
        if not self.tickLocs:
            self._setTickLocs()
        if self.horiz:
            lineSize = self._lineL, self._lineW
            tickSize = self._lineW, self._tickL
        else:
            lineSize = self._lineW, self._lineL
            tickSize = self._tickL, self._lineW
        self.line = GratingStim(win=self.win, pos=self.pos, color=self._borderColor.copy(), colorSpace=self.colorSpace,
                                size=lineSize, sf=0, units=self.units,
                                autoLog=False)
        self.tickLines = ElementArrayStim(win=self.win, units=self.units,
                                          nElements=len(self.ticks),
                                          xys=self.tickLocs,
                                          elementMask=None,
                                          colors=self._borderColor.copy(), colorSpace = self.colorSpace,
                                          opacities=self._borderColor.alpha,
                                          sizes=tickSize, sfs=0,
                                          autoLog=False)

        self.labelObjs = []
        if self.labels is not None:
            if not self.labelLocs:
                self._setLabelLocs()
            if self.horiz:
                alignHoriz = 'center'
                if not self.flip:
                    alignVert = 'top'
                    self.labelLocs -= [0, self._tickL]
                else:
                    alignVert = 'bottom'
                    self.labelLocs += [0, self._tickL]
            else:  # vertical
                alignVert = 'center'
                if not self.flip:
                    alignHoriz = 'right'
                    self.labelLocs -= [self._tickL, 0]
                else:
                    alignHoriz = 'left'
                    self.labelLocs += [self._tickL, 0]
            for tickN, label in enumerate(self.labels):
                if label is None:
                    continue

                obj = TextStim(self.win, label, font=self.font,
                               anchorHoriz=alignHoriz, anchorVert=alignVert,
                               units=self.units, color=self._foreColor.copy(), colorSpace=self.colorSpace,
                               pos=self.labelLocs[tickN, :],
                               height=self.labelHeight, 
                               wrapWidth=self.labelWrapWidth,
                               autoLog=False)
                self.labelObjs.append(obj)

        if self.units == 'norm':
            # convert to make marker round
            aspect = self.win.size[0] / self.win.size[1]
            markerSize = np.array([self._tickL, self._tickL * aspect])
        else:
            markerSize = self._tickL

        self.marker = Circle(self.win, units=self.units,
                             size=markerSize,
                             fillColor=self._fillColor,
                             autoLog=False)

        # create a rectangle to check for clicks
        self.validArea = Rect(self.win, units=self.units,
                              pos=self.pos,
                              size=[d * 1.1 for d in self.size],
                              lineColor='DarkGrey',
                              autoLog=False)

    @attributeSetter
    def pos(self, newPos):
        """Set position of slider

        Parameters
        ----------
        value: tuple, list
            The new position of slider
        """
        newPos = np.array(newPos)
        oldPos = self.__dict__['pos']
        self.__dict__['pos'] = newPos
        deltaPos = np.subtract(newPos, oldPos)
        self.line.pos += deltaPos
        self.validArea.pos += deltaPos
        self.marker.pos += deltaPos
        self.tickLines.xys += deltaPos
        for label in self.labelObjs:
            label.pos += deltaPos

    def _ratingToPos(self, rating):
        try:
            n = len(rating)
        except:
            n = 1
        pos = np.ones([n, 2], 'f') * self.pos

        scaleMag = self.ticks[-1] - self.ticks[0]
        scaleLow = self.ticks[0]
        if self.horiz:
            pos[:, 0] = (((rating - scaleLow) / scaleMag - 0.5) * self._lineL +
                         self.pos[0])
        else:
            pos[:, 1] = (((rating - scaleLow) / scaleMag - 0.5) * self._lineL +
                         self.pos[1])

        return pos

    def _posToRating(self, pos):
        scaleMag = self.ticks[-1] - self.ticks[0]
        scaleLow = self.ticks[0]
        if self.horiz:
            rating = (((pos[0] - self.pos[0]) / self._lineL + 0.5)
                      * scaleMag + scaleLow)
        else:
            rating = (((pos[1] - self.pos[1]) / self._lineL + 0.5)
                      * scaleMag + scaleLow)

        return rating

    def _setTickLocs(self):
        """ Calculates the locations of the line, tickLines and labels from
        the rating info
        """
        try:
            n = len(self.ticks)
        except TypeError:
            self.categorical = True
        if self.categorical:
            self.ticks = np.arange(len(self.labels))
            self.granularity = 1.0

        self.tickLocs = self._ratingToPos(self.ticks)

    def _setLabelLocs(self):
        """ Calculates the locations of the line, tickLines and labels from
        the rating info
        """
        if not self.labels:
            self.labelLocs = []
            return
        labelFractions = np.arange(len(self.labels)) / (len(self.labels) - 1)
        tickIndices = np.round(labelFractions * (len(self.tickLocs) - 1))
        self.labelLocs = self.tickLocs[tickIndices.astype('int')]

    def _granularRating(self, rating):
        """Handle granularity for the rating"""
        if rating is not None:
            if self.granularity > 0:
                rating = round(rating / self.granularity) * self.granularity
                rating = round(rating, 8)  # or gives 1.9000000000000001
            rating = max(rating, self.ticks[0])
            rating = min(rating, self.ticks[-1])
        return rating

    @attributeSetter
    def rating(self, rating):
        """The most recent rating from the participant or None.
        Note that the position of the marker can be set using current without
        looking like a change in the marker position"""
        rating = self._granularRating(rating)
        self.markerPos = rating
        if self.categorical and (rating is not None):
            rating = self.labels[int(round(rating))]
        self.__dict__['rating'] = rating

    @property
    def value(self):
        """Synonymous with .rating"""
        return self.rating
    @value.setter
    def value(self, val):
        self.rating = val

    @attributeSetter
    def markerPos(self, rating):
        """The position on the scale where the marker should be. Note that
        this does not alter the value of the reported rating, only its visible
        display.
        Also note that this position is in scale units, not in coordinates"""
        rating = self._granularRating(rating)
        if ('markerPos' not in self.__dict__ or not np.alltrue(
                self.__dict__['markerPos'] == rating)):
            self.__dict__['markerPos'] = rating
            self._updateMarkerPos = True

    def recordRating(self, rating, rt=None, log=None):
        """Sets the current rating value
        """
        rating = self._granularRating(rating)
        setAttribute(self, attrib='rating', value=rating, operation='', log=log)
        if rt is None:
            self.rt = self.responseClock.getTime()
        else:
            self.rt = rt
        self.history.append((rating, self.rt))
        self._updateMarkerPos = True

    def getRating(self):
        """Get the current value of rating (or None if no response yet)
        """
        return self.rating

    def getRT(self):
        """Get the RT for most recent rating (or None if no response yet)
        """
        return self.rt

    def getMarkerPos(self):
        """Get the current marker position (or None if no response yet)
        """
        return self.markerPos

    def setMarkerPos(self, rating):
        """Set the current marker position (or None if no response yet)

        Parameters
        ----------
        rating : int or float
            The rating on the scale where we want to set the marker
        """
        if self._updateMarkerPos:
            self.marker.pos = self._ratingToPos(rating)
            self.markerPos = rating
            self._updateMarkerPos = False
        self.marker.draw()

    def draw(self):
        """Draw the Slider, with all its constituent elements on this frame
        """
        self.getMouseResponses()
        # self.validArea.draw()
        self.line.draw()
        self.tickLines.draw()
        if self.markerPos is not None:
            if self._updateMarkerPos:
                self.marker.pos = self._ratingToPos(self.markerPos)
                self._updateMarkerPos = False
            self.marker.draw()
        for label in self.labelObjs:
            label.draw()
        # we started drawing to reset clock on flip
        if self.status == NOT_STARTED:
            self.win.callOnFlip(self.responseClock.reset)
            self.status = STARTED

    def getHistory(self):
        """Return a list of the subject's history as (rating, time) tuples.

        The history can be retrieved at any time, allowing for continuous
        ratings to be obtained in real-time. Both numerical and categorical
        choices are stored automatically in the history.
        """
        return self.history

    def setReadOnly(self, value=True, log=None):
        """When the rating scale is read only no responses can be made and the
        scale contrast is reduced

        Parameters
        ----------
        value : bool (True)
            The value to which we should set the readOnly flag
        log : bool or None
            Force the autologging to occur or leave as default

        """
        setAttribute(self, 'readOnly', value, log)
        if value == True:
            self.contrast = 0.5
        else:
            self.contrast = 1.0

    @attributeSetter
    def contrast(self, contrast):
        """Set all elements of the Slider (labels, ticks, line) to a contrast

        Parameters
        ----------
        contrast
        """
        self.marker.contrast = contrast
        self.line.contrast = contrast
        self.tickLines.contrasts = contrast
        for label in self.labelObjs:
            label.contrast = contrast

    def getMouseResponses(self):
        """Instructs the rating scale to check for valid mouse responses.

        This is usually done during the draw() method but can be done by the
        user as well at any point in time. The rating will be returned but
        will ALSO automatically be set as the current rating response.

        While the mouse button is down we will alter self.markerPos
        but don't set a value for self.rating until button comes up

        Returns
        ----------
        A rating value or None
        """
        if self.readOnly:
            return
        click = bool(self.mouse.getPressed()[0])
        xy = self.mouse.getPos()

        if click:
            # Update current but don't set Rating (mouse is still down)
            # Dragging has to start inside a "valid" area (i.e., on the
            # slider), but may continue even if the mouse moves away from
            # the slider, as long as the mouse button is not released.
            if (self.validArea.contains(self.mouse, units=self.units) or
                    self._dragging):
                self.markerPos = self._posToRating(xy)  # updates marker
                self._dragging = True
        else:  # mouse is up - check if it *just* came up
            if self._dragging:
                self._dragging = False
                if self.markerPos is not None:
                    self.recordRating(self.markerPos)
                return self.markerPos
            else:
                # is up and was already up - move along
                return None

        self._mouseStateXY = xy

    # Overload color setters so they set sub-components
    @property
    def foreColor(self):
        ColorMixin.foreColor.fget(self)
    @foreColor.setter
    def foreColor(self, value):
        ColorMixin.foreColor.fset(self, value)
        # Set color for all labels
        if hasattr(self, "labelObjs"):
            for obj in self.labelObjs:
                obj.color = self._foreColor.copy()

    @property
    def fillColor(self):
        ColorMixin.fillColor.fget(self)
    @fillColor.setter
    def fillColor(self, value):
        ColorMixin.fillColor.fset(self, value)
        # Set color for marker
        if hasattr(self, "marker"):
            self.marker.fillColor = self._fillColor.copy()

    @property
    def borderColor(self):
        ColorMixin.borderColor.fget(self)
    @borderColor.setter
    def borderColor(self, value):
        ColorMixin.borderColor.fset(self, value)
        # Set color for lines
        if hasattr(self, "line"):
            self.line.color = self._borderColor.copy()
        if hasattr(self, "tickLines"):
            self.tickLines.colors = self._borderColor.copy()

    knownStyles = ['slider', 'rating', 'radio', 'scrollbar']
    legacyStyles = []
    knownStyleTweaks = ['labels45', 'triangleMarker']
    legacyStyleTweaks = ['whiteOnBlack']

    @attributeSetter
    def style(self, style):
        """Sets some predefined styles or use these to create your own.

        If you fancy creating and including your own styles that would be great!

        Parameters
        ----------
        style: string

            Known styles currently include:

                'rating': the marker is a circle
                'slider': looks more like an application slider control
                'whiteOnBlack': a sort of color-inverse rating scale
                'scrollbar': looks like a scrollbar for a window

            Styles cannot be combined in a list - they are discrete

        """
        self.__dict__['style'] = style

        # Legacy: If given a list (as was once the case), take the first style
        if isinstance(style, (list, tuple)):
            styles = style
            style = "rating"
            for val in styles:
                # If list contains a style, use it
                if val in self.knownStyles + self.legacyStyles:
                    style = val
                # Apply any tweaks
                if val in self.knownStyleTweaks + self.legacyStyleTweaks:
                    self.styleTweaks += val

        if style == 'rating':
            pass  # this is just the default

        if style == 'slider':
            # make it more like a slider using a box instead of line
            self.line = Rect(self.win, units=self.units,
                             pos=self.pos,
                             size=self.size,
                             fillColor=self._borderColor.copy(),
                             lineColor=None,
                             autoLog=False)
            self.line._fillColor.alpha *= 0.2
            if self.horiz:
                markerW = self.size[0] * 0.01
                markerH = self.size[1] * 0.8
            else:
                markerW = self.size[0] * 0.8
                markerH = self.size[1] * 0.01

            self.marker = Rect(self.win, units=self.units,
                               size=[markerW, markerH],
                               fillColor=self._fillColor,
                               lineColor=None,
                               autoLog=False)

        if style == 'radio':
            # no line, ticks are circles
            self.line.opacity = 0
            # ticks are circles
            self.tickLines.sizes = (self._tickL, self._tickL)
            self.tickLines.elementMask = 'circle'
            # marker must be smalle than a "tick" circle
            self.marker.size = self._tickL * 0.7
            self.marker.fillColor = self._fillColor.copy()

        if style == 'scrollbar':
            # Make marker the full height and 20% of the width of the slider
            markerSz = self.size[0]*0.2 if self.horiz else self.size[1]*0.2
            w, h = self.size
            self.marker = Rect(self.win, units=self.units,
                               size=[markerSz, h] if self.horiz else [w, markerSz],
                               fillColor=self._fillColor,
                               lineColor=None,
                               autoLog=False)
            # Make the line a translucent box
            self.line = Rect(self.win, units=self.units,
                             pos=self.pos,
                             size=[w+markerSz, h] if self.horiz else [w, h+markerSz],
                             fillColor=self._borderColor.copy(),
                             lineColor=None,
                             autoLog=False)
            self.line._fillColor.alpha *= 0.05
            self.tickLines = Rect(self.win, size=(0,0), lineColor=None, fillColor=None)

        # Legacy: If given a tweak, apply it as a tweak rather than a style
        if style in self.knownStyleTweaks + self.legacyStyleTweaks:
            self.styleTweaks.append(style)

    @attributeSetter
    def styleTweaks(self, styleTweaks):
        """Sets some predefined style tweaks or use these to create your own.

        If you fancy creating and including your own style tweaks that would be great!

        Parameters
        ----------
        styleTweaks: list of strings

            Known style tweaks currently include:

                'triangleMarker': the marker is a triangle
                'labels45': the text is rotated by 45 degrees

            Legacy style tweaks include:

                'whiteOnBlack': a sort of color-inverse rating scale

            Legacy style tweaks will work if set in code, but are not exposed in Builder as they are redundant

            Style tweaks can be combined in a list e.g. `['labels45']`

        """
        self.__dict__['styleTweaks'] = styleTweaks

        if 'triangleMarker' in styleTweaks:
            if self.horiz and self.flip:
                ori = -90
            elif self.horiz:
                ori = -90
            elif not self.horiz and self.flip:
                ori = 180
            else:
                ori = 0

            markerSize = min(self.size) * 2
            self.marker = ShapeStim(self.win, units=self.units,
                                    vertices=[[0, 0], [0.5, 0.5], [0.5, -0.5]],
                                    size=markerSize,
                                    ori=ori,
                                    fillColor=self._fillColor.copy(),
                                    lineColor=None,
                                    lineWidth=0,
                                    autoLog=False)

        if 'labels45' in styleTweaks:
            for label in self.labelObjs:
                if self.flip:
                    label.alignHoriz = 'left'
                else:
                    label.alignHoriz = 'right'
                label.ori = -45

        # Legacy
        if 'whiteOnBlack' in styleTweaks:
            self.line.color = 'black'
            self.tickLines.colors = 'black'
            self.marker.color = 'white'
            for label in self.labelObjs:
                label.color = 'white'