"""Definition of colormaps"""
import matplotlib.cm as cm
import matplotlib.colors as mpcolors


def nwsprecip():
    """A color ramp used by NWS on NTP plots

    Changes
     - modified the reds a bit to provide a larger gradient
     - added two light brown colors at the low end to allow for more levels
     - removed perhaps a bad orange color and remove top white color
    """
    cpool = ["#cbcb97", "#989865",
             "#00ebe7", "#00a0f5", "#000df5", "#00ff00", "#00c600",
             "#008e00", "#fef700", "#e5bc00", "#ff8500", "#ff0000",
             "#af0000", "#640000", "#ff00fe", "#a152bc"]
    cmap = mpcolors.ListedColormap(cpool, 'nwsprecip')
    cmap.set_over('#FFFFFF')
    cmap.set_under('#FFFFFF')
    cmap.set_bad("#FFFFFF")
    cm.register_cmap(cmap=cmap)
    return cmap


def nwssnow():
    """A Color Ramp Suggested by the NWS for Snowfall"""
    cpool = [[0.74117647, 0.84313725, 0.90588235],
             [0.41960784, 0.68235294, 0.83921569],
             [0.19215686, 0.50980392, 0.74117647],
             [0.03137255, 0.31764706, 0.61176471],
             [0.03137255, 0.14901961, 0.58039216],
             [1.,  1.,  0.58823529],
             [1.,  0.76862745, 0.],
             [1.,  0.52941176, 0.],
             [0.85882353,  0.07843137, 0.],
             [0.61960784,  0., 0.],
             [0.41176471,  0., 0.]]
    cmap = mpcolors.ListedColormap(cpool, 'nwssnow')
    cmap.set_over([0.16862745,  0., 0.18039216])
    cmap.set_under('#FFFFFF')
    cmap.set_bad("#FFFFFF")
    cm.register_cmap(cmap=cmap)
    return cmap


def james2():
    """David James suggested color ramp Yellow to Brown"""
    cpool = ['#FFFF80', '#FFEE70', '#FCDD60', '#FACD52', '#F7BE43', '#F5AF36',
             '#E69729', '#CC781F', '#B35915', '#9C400E', '#822507', '#6B0000']
    cmap3 = mpcolors.ListedColormap(cpool, 'james2')
    cmap3.set_over("#000000")
    cmap3.set_under("#FFFFFF")
    cmap3.set_bad("#FFFFFF")
    cm.register_cmap(cmap=cmap3)
    return cmap3


def james():
    """David James suggested color ramp Yellow to Blue """
    cpool = ['#FFFF80', '#CDFA64', '#98F046', '#61E827', '#3BD923', '#3FC453',
             '#37AD7A', '#26989E', '#217AA3', '#215394', '#1B3187', '#0C1078']
    cmap3 = mpcolors.ListedColormap(cpool, 'james')
    cmap3.set_over("#000000")
    cmap3.set_under("#FFFFFF")
    cmap3.set_bad("#FFFFFF")
    cm.register_cmap(cmap=cmap3)
    return cmap3


def whitebluegreenyellowred():
    ''' Rip off NCL's WhiteBlueGreenYellowRed '''
    cpool = ['#cfedfb', '#cdecfb', '#caebfb', '#c7eafa', '#c5e9fa', '#c2e8fa',
             '#bfe7fa', '#bde6fa', '#bae5f9', '#b7e4f9', '#b5e3f9', '#b2e2f9',
             '#b0e1f9', '#ade0f8', '#aadff8', '#a8def8', '#a5ddf8', '#a2dcf7',
             '#9ddaf7', '#9bd8f6', '#98d6f5', '#96d4f3', '#94d2f2', '#92d0f1',
             '#8fcef0', '#8dccee', '#8bcaed', '#88c8ec', '#86c5eb', '#84c3ea',
             '#81c1e8', '#7fbfe7', '#7dbde6', '#7bbbe5', '#78b9e4', '#76b7e2',
             '#74b5e1', '#71b3e0', '#6fb1df', '#6dafdd', '#6aaddc', '#68abdb',
             '#66a9da', '#64a7d9', '#61a5d7', '#5fa3d6', '#5da0d5', '#5a9ed4',
             '#589cd3', '#569ad1', '#5398d0', '#5196cf', '#4f94ce', '#4d92cc',
             '#488eca', '#488fc6', '#4890c3', '#4891bf', '#4892bc', '#4893b8',
             '#4894b5', '#4895b1', '#4896ad', '#4897aa', '#4899a6', '#489aa3',
             '#489b9f', '#489c9c', '#489d98', '#489e94', '#489f91', '#48a08d',
             '#48a18a', '#49a286', '#49a383', '#49a47f', '#49a57c', '#49a678',
             '#49a774', '#49a871', '#49a96d', '#49aa6a', '#49ac66', '#49ad63',
             '#49ae5f', '#49af5b', '#49b058', '#49b154', '#49b251', '#49b34d',
             '#49b546', '#4eb647', '#53b847', '#57b948', '#5cbb48', '#61bc49',
             '#66bd4a', '#6abf4a', '#6fc04b', '#74c14b', '#79c34c', '#7ec44d',
             '#82c64d', '#87c74e', '#8cc84e', '#91ca4f', '#96cb50', '#9acc50',
             '#9fce51', '#a4cf51', '#a9d152', '#add252', '#b2d353', '#b7d554',
             '#bcd654', '#c1d755', '#c5d955', '#cada56', '#cfdc57', '#d4dd57',
             '#d9de58', '#dde058', '#e2e159', '#e7e25a', '#ece45a', '#f0e55b',
             '#f5e75b', '#fae85c', '#fae55b', '#fae159', '#fade58', '#f9da56',
             '#f9d755', '#f9d454', '#f9d052', '#f9cd51', '#f9c950', '#f9c64e',
             '#f9c34d', '#f8bf4b', '#f8bc4a', '#f8b849', '#f8b547', '#f8b246',
             '#f8ae45', '#f8ab43', '#f7a742', '#f7a440', '#f7a03f', '#f79d3e',
             '#f79a3c', '#f7963b', '#f7933a', '#f68f38', '#f68c37', '#f68935',
             '#f68534', '#f68233', '#f67e31', '#f67b30', '#f6782f', '#f5742d',
             '#f5712c', '#f56a29', '#f46829', '#f36629', '#f26429', '#f16229',
             '#f06029', '#ef5e29', '#ef5c29', '#ee5a29', '#ed5829', '#ec5629',
             '#eb5429', '#ea5229', '#e95029', '#e84e29', '#e74c29', '#e64a29',
             '#e54829', '#e44629', '#e44328', '#e34128', '#e23f28', '#e13d28',
             '#e03b28', '#df3928', '#de3728', '#dd3528', '#dc3328', '#db3128',
             '#da2f28', '#d92d28', '#d92b28', '#d82928', '#d72728', '#d62528',
             '#d52328', '#d31f28', '#d11f28', '#cf1e27', '#ce1e27', '#cc1e26',
             '#ca1e26', '#c81d26', '#c71d25', '#c51d25', '#c31d24', '#c11c24',
             '#c01c24', '#be1c23', '#bc1b23', '#ba1b22', '#b91b22', '#b71b22',
             '#b51a21', '#b31a21', '#b21a20', '#b01a20', '#ae191f', '#ac191f',
             '#ab191f', '#a9191e', '#a7181e', '#a5181d', '#a4181d', '#a2171d',
             '#a0171c', '#9e171c', '#9d171b', '#9b161b', '#99161b', '#97161a',
             '#96161a', '#921519']
    cmap3 = mpcolors.ListedColormap(cpool, 'whitebluegreenyellowred')
    cmap3.set_over("#000000")
    cmap3.set_under("#FFFFFF")
    cmap3.set_bad("#FFFFFF")
    cm.register_cmap(cmap=cmap3)
    return cmap3


def maue():
    """ Pretty color ramp Dr Ryan Maue uses """
    cpool = ["#e6e6e6", "#d2d2d2", "#bcbcbc", "#969696", "#646464",
             "#1464d2", "#1e6eeb", "#2882f0", "#3c96f5", "#50a5f5", "#78b9fa",
             "#96d2fa", "#b4f0fa", "#e1ffff",
             "#0fa00f", "#1eb41e", "#37d23c", "#50f050", "#78f573", "#96f58c",
             "#b4faaa", "#c8ffbe",
             "#ffe878", "#ffc03c", "#ffa000", "#ff6000", "#ff3200", "#e11400",
             "#c00000", "#a50000", "#643c32",
             "#785046", "#8c645a", "#b48c82", "#e1beb4", "#f0dcd2", "#ffc8c8",
             "#f5a0a0", "#e16464", "#c83c3c"]

    cmap3 = mpcolors.ListedColormap(cpool, 'maue')
    cmap3.set_over("#000000")
    cmap3.set_under("#FFFFFF")
    cmap3.set_bad("#FFFFFF")
    cm.register_cmap(cmap=cmap3)
    return cmap3
