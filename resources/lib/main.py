
from __future__ import unicode_literals
import xbmc
import xbmcgui
from xbmcaddon import Addon
from xbmc import executebuiltin
from xbmcgui import Dialog
from codequick import Route, run, Listitem, Resolver, Script
from codequick.script import Settings
from codequick.utils import keyboard
import sys
import inputstreamhelper
import urlquick
import requests
import urllib.request
import html
from urllib.parse import urlencode, urlparse
from time import time, sleep
from datetime import datetime, timedelta, date
import json
import m3u8

from .utils import uaheaders, getBool, getHeaders, getChannelHeaders, getCachedDictionary, quality_to_enum, dtnow, strdtnow, notif, isLoggedIn, login as ULogin, logout as ULogout, sendOTP, runPg, runPgMain, runPgRefresh, getFeatured, getTabData, getCatData, getChData, getSearchData, dm, appkey, check_addon, _setup, cleanLocalCache, epgcheckEpoch
from .constants import filterBy, tabsDict, GSET, SSET, CHANNELS_SRC, GET_CHANNEL_URL, CATCHUP_SRC, PAST_PROGS_EPISODES, PBV1URL, EPG_SRC, M3U_SRC, EPG_URL, TVAPIMEDIA, ANM, AID, ICO, FNR, IMG, IMG_POSTER, PTH, PID, IID, CAROUSEL, devicetype, oprsys, osver, usergroup, useragent, httpuseragent, vercode
from .chdata import intUrls, dai, zfpg

dictionary = getCachedDictionary()   
LMAP = dictionary.get("languageIdMapping")
CMAP = dictionary.get("channelCategoryMapping")
MAPS = [LMAP, CMAP]
channels = urlquick.get(CHANNELS_SRC, verify=False, headers=uaheaders, max_age=-1).json().get("result")
jtCh = len(channels)
isPbapiv1 = True if GSET("pbapiv") == "v1" else False
fltraL = getBool("filteraddlist")
hdsdch = GSET("hdsdch")
Ch = " Channels"
Livetext = "[COLOR red] • Live [/COLOR]"
Ctchp = "Catchup"
pastprog = "Past Programs"
pastepis = "Past Episodes"
prginfo = "Program Info"
Chguide = "8 Days Guide"
Chctchp = "7 Days " + Ctchp
mpath = runPg[-15:] + "main:"
progDT = ' %a, %d %b %I:%M%p '
dtfts = '%Y%m%dT%H%M%S'
dtftsStart = ' %I:%M%p -'
dtftsEnd = ' %I:%M%p, %a %d %b '
menu = {"show_listby": filterBy, "show_fltrhdsdch": "HD / SD / HD & SD" + Ch, "show_allch": "All " + str(jtCh) + Ch, "show_featured": "Featured • " + strdtnow[3:-12], "carousel_list": "Carousel", "show_search": "Search", "show_settings": "Settings"}
menuLen = len(list(menu))
art = {"thumb": ICO, "icon": ICO, "fanart": FNR}
onlineEPG = GSET("epg_url") != ""
EPG_DATA = EPG_URL if onlineEPG else EPG_SRC

@Route.register
def root(plugin):
    for f in filterBy:
        yield Listitem.from_dict(**{
            "label": f,
            "art": art,
            "callback": Route.ref(mpath + list(menu)[0]),
            "params": {"by": f}
        })
    for g in range(1, menuLen):
        yield Listitem.from_dict(**{
            "label": list(menu.values())[g],
            "art": art,
            "callback": Route.ref(mpath + list(menu)[g])
        })

@Route.register
def show_listby(plugin, by):
    CONFIG = {}
    CMAP.pop("14")
    CMAP.pop("19")
    for c in range(len(filterBy)):
        OKey = list(MAPS[c])[-1]
        OtherKey = int(OKey) + 1
        MAPS[c].update({str(OtherKey): "Other " + filterBy[c]})
        CONFIG.update({filterBy[c]: list(MAPS[c].values())})
        MAPS[c].popitem()
    for fltr in CONFIG[by]:
        if fltraL:
            if not getBool(fltr):
               continue
        yield Listitem.from_dict(**{
               "label": fltr,
               "art": art,
               "callback": show_channels,
               "params": {"LanCat": fltr, "by": by}
           })

def mapId(channel):
    def getmapId(MAP, Id):
        lcid = str(channel.get(Id))
        if lcid not in MAP:
            OtherLC = "Other " + Id.replace("channel", "").replace("Id", "s").replace("y", "ie").capitalize()
            MAP[lcid] = OtherLC
        return MAP[lcid]
    Lan = getmapId(LMAP, "channelLanguageId")
    Cat = getmapId(CMAP, "channelCategoryId")    
    return Lan, Cat

def tpurl(channel_id):            
    redirecturl = requests.get(dai % intUrls[channel_id], allow_redirects=False).headers.get('Location')                        
    tpslurl = redirecturl.replace(urlparse(redirecturl).hostname, "tataplaymt.slivcdn.com").split("&")                    
    return tpslurl[0] + "&deviceId=TataPlayLinearDigital-Server&partner=TataPlayLinearDigital&platform=Android&user-agent=ott&sku_name=Free"

def intRdr(channel_id):
    slsrc = GSET("slsrc")
    if len(intUrls[channel_id]) == 22:
        return dai % intUrls[channel_id] if int(slsrc) == 1 else tpurl(channel_id)
    else:
        return zfpg % intUrls[channel_id]

def chlogo(channel):
    return IMG + channel.get("logoUrl")

def hasCatchup(channel):
    return True if channel.get("isCatchupAvailable") else False

def contextMenu(listitm, funct, flabel, csid, flag):
    listitm.context.container(funct, flabel, csid, flag) if "Past" in flabel else listitm.context.container(funct, flabel, 0, csid, flag)

def returnDT(each, epoch, dtstamp, utc=False):
    return datetime.fromtimestamp(int(each.get(epoch, 0)*.001)).strftime(dtstamp) if not utc else datetime.utcfromtimestamp(int(each.get(epoch, 0)*.001)).strftime(dtstamp)

def list_channels(channel):
    channel_id = channel.get("channel_id")
    channel_name = channel.get("channel_name")
    if getBool("numaddlist"):
        channel_name = "  ".join([str(int(channel.get("channel_order")) + 1), channel_name])
    art["thumb"] = art["icon"] = art["fanart"] = chlogo(channel)
    listchannels = Listitem.from_dict(**{
            "label": channel_name,
            "art": art,
            "callback": play,
            "params": {
                "channel_id": channel_id
            }
        })
    if channel_id < 4000:
        contextMenu(listchannels, show_epgtvg, Chguide, channel_id, False)
    if hasCatchup(channel):
        contextMenu(listchannels, past_progs_ep, pastprog, channel_id, False)
        contextMenu(listchannels, show_epgtvg, Chctchp, channel_id, True)
    return listchannels

@Route.register
def show_channels(plugin, LanCat, by):
    def fltr(channel):
        Lan, Cat = mapId(channel)
        LC = [Lan, Cat]
        for i in range(len(filterBy)):
            if by == filterBy[i]:
               return LC[i] == LanCat
    for channel in filter(fltr, channels):
        if fltraL:
            Lan, Cat = mapId(channel)
            if not getBool(Lan):
                continue
            if not getBool(Cat):
                continue
        isHD = channel.get("isHD")
        if int(hdsdch) == 1 and not isHD:
            continue
        if int(hdsdch) == 2 and isHD:
            continue
        yield list_channels(channel)

@Route.register
def show_fltrhdsdch(plugin):
    hdialog = Dialog()
    HDSDSel = hdialog.select(Ch + " Resolution", ["HD" + Ch, "SD" + Ch, "HD & SD" + Ch])
    for channel_id, channel in enumerate(channels):
        if fltraL:
            Lan, Cat = mapId(channel)
            if not getBool(Lan):
                continue
            if not getBool(Cat):
                continue
        isHD = channel.get("isHD")
        if HDSDSel == -1:
            sys.exit()
        if HDSDSel == 0 and not isHD:
            continue
        if HDSDSel == 1 and isHD:
            continue
        yield list_channels(channel)
    return None

@Route.register
def show_allch(plugin):
    for channel_id, channel in enumerate(channels):
        yield list_channels(channel)

@Route.register
def tabs_cat(plugin, tabid):
    tabData = getTabData(tabid)
    for each in tabData:
        cat_id = each.get("cat_id")
        type = each.get("type")
        displayType = each.get("displayType")
        if type != "svod" and displayType != "vodCategories":
            yield Listitem.from_dict(**{
               "label": each.get("name"),
               "art": art,
               "callback": see_cat,
               "params": {"cat_id": cat_id}
          })

@Route.register
def see_cat(plugin, cat_id):
    catData = getCatData(cat_id)
    for each in catData[0]["data"]:
        isNow = each.get("showStatus") == "Now"
        isCatchup = each.get("showStatus") == "catchup"
        isChannel = each.get("setType") == "channel"
        isVod = each.get("setType") == "svod"
        if not isVod:
            channel_id = each.get("channel_id")
            showtime = None if isNow else each.get("showtime", "").replace(":", "")
            srno = each.get("srno", "")
            begin = returnDT(each, "startEpoch", dtfts, True)
            end = returnDT(each, "endEpoch", dtfts, True)
            timing = returnDT(each, "startEpoch", progDT, False)
            showname = each.get("showname")
            showname = "[COLOR yellow]%s[/COLOR]" % showname if isCatchup else "[COLOR red]%s[/COLOR]" % showname
            chlabel = " | ".join([showname, each.get("channel_name"), timing])
            art["thumb"] = art["icon"] = art["fanart"] = IMG_POSTER + each.get("episodePoster")
        catprog_dict = {
            "label": chlabel,
            "art": art,
            "info": {"title": chlabel,
                            'originaltitle': chlabel} if isVod else {
                            "title": chlabel,
                            'originaltitle': chlabel ,
                            "tvshowtitle": chlabel ,
                            "plot": each.get("description"),
                            "episodeguide": each.get("episode_desc"),
                            "episode": 0 if each.get("episode_num") == -1 else each.get("episode_num"),
                            "cast": each.get("starCast", "").split(', '),
                            "director": each.get("director"),
                            "duration": each.get("duration")*60,
                        },
            "callback": play,
            "params": {"channel_id": channel_id}
        }
        if isCatchup and not isChannel:
            catprog_dict["params"].update({"showtime": showtime, "srno": srno, "programId": srno , "begin": begin, "end": end})
        catprogli = Listitem.from_dict(**catprog_dict)
        if not isVod:
            catprogli.context.container(programInfo, prginfo, srno)
        yield catprogli

@Route.register
def carousel_list(plugin):
    for tabid in list(tabsDict.keys()):
        yield Listitem.from_dict(**{
            "label": tabsDict[tabid] + " Carousel",
            "art": art,
            "callback": Route.ref(mpath + "carousel_prog"),
            "params": {"tabid": tabid}
        })

@Route.register
def carousel_prog(plugin, tabid):
    carouselData = urlquick.get(CAROUSEL.format(tabid), verify=False, headers=uaheaders, max_age=-1).json().get("promotionalData", [])
    for each in carouselData:
        isNow = each.get("showStatus") == "Now"
        isCatchup = each.get("showStatus") == "catchup"
        isChannel = each.get("setType") == "channel"
        isVod = each.get("setType") == "svod"
        if not isVod:
            channel_id = each.get("channel_id")
            showtime = each.get("showtime", "").replace(":", ""),
            srno = each.get("srno", "")
            begin = returnDT(each, "startEpoch", dtfts, True)
            end = returnDT(each, "endEpoch", dtfts, True)
            timing = returnDT(each, "startEpoch", progDT, False)
            showname = each.get("showname")
            showname = " [COLOR yellow]%s[/COLOR]" % showname if isCatchup else "[COLOR red]%s[/COLOR]" % showname
            chlabel = " | ".join([showname, each.get("channel_name"), timing])
            art["thumb"] = art["icon"] = art["fanart"] = IMG_POSTER + each.get("episodePoster")
            carprog_dict = {
               "label": chlabel,
               "art": art,
               "info":  {  "title": chlabel,
                               "originaltitle": chlabel ,
                               "tvshowtitle": chlabel ,
                               "plot": each.get("description"),
                               "episodeguide": each.get("episode_desc"),
                               "episode": 0 if each.get("episode_num") == -1 else each.get("episode_num"),
                               "cast": each.get("starCast", "").split(', '),
                               "director": each.get("director"),
                               "duration": each.get("duration")*60,
                        },
               "callback": play,
               "params": {"channel_id": channel_id}
           }
            if isCatchup and not isChannel:
                carprog_dict["params"].update({"showtime": showtime, "srno": srno, "programId": srno , "begin": begin, "end": end})
            carprogli = Listitem.from_dict(**carprog_dict)
            if not isVod:
                carprogli.context.container(programInfo, prginfo, srno)
            yield carprogli

@Route.register
def search_listing(plugin, items):
    searchDataDict = getSearchData(False)
    resultList = searchDataDict[items]
    isChannels = items == "channels"
    isCatchup = items == "catchup"
    if isChannels or isCatchup:
        for each in resultList:
            channel_name = each.get("channel_name")
            channel_id = each.get("channel_id")
            art["thumb"] = art["icon"] = art["fanart"] = chlogo(each) if isChannels else IMG_POSTER + each.get("episodePoster")
            search_dict = {
            "label": channel_name,
            "art": art,
            "callback": play,
            "params": {"channel_id": channel_id,}
            }
            if isChannels:
                searchli = Listitem.from_dict(**search_dict)
                contextMenu(searchli, show_epgtvg, Chguide, channel_id, False)
                if hasCatchup(each):
                    contextMenu(searchli, past_progs_ep, pastprog, channel_id, False)                
                    contextMenu(searchli, show_epgtvg, Chctchp, channel_id, True)
                yield searchli
            elif isCatchup:
                timing = returnDT(each, "startEpoch", progDT, False)
                showname = html.unescape(each.get("showname"))
                showname = "[COLOR yellow]%s[/COLOR]" % showname
                channel_name = " | ".join([showname, channel_name, timing])
                showId = each.get("showId", "")
                srno = each.get("srno", "")
                isPastEpisode = each.get("isPastEpisode")
                search_dict["params"].update({"showtime": each.get("showtime", "").replace(":", ""), "srno": srno, "programId": srno, "begin": returnDT(each, "startEpoch", dtfts, True), "end": returnDT(each, "endEpoch", dtfts, True)})
                search_dict.update({"info": {
                            "title": channel_name,
                            'originaltitle': channel_name,
                            "tvshowtitle": channel_name,
                            "plot": each.get("description"),
                            "episodeguide": each.get("episode_desc"),
                            "episode": 0 if each.get("episode_num") == -1 else each.get("episode_num"),
                            "cast": each.get("starCast", "").split(', '),
                            "director": each.get("director"),
                            "duration": each.get("duration")*60,
                        }})
                searchli = Listitem.from_dict(**search_dict)
                if isPastEpisode:
                    contextMenu(searchli, past_progs_ep, pastepis, showId, True)
                searchli.context.container(programInfo, prginfo, srno)
                yield searchli

@Route.register
def show_search(plugin):
    searchData = getSearchData(True)
    result_cat = []
    if searchData != {}:
        result_cat = list(searchData.keys())
    else:
        notif("No search results!")
        return
    for ritm in ['live','movies', 'shows', 'videos', 'games']:
        result_cat.remove(ritm)
    for items in result_cat:
        if searchData[items] != []:
            yield Listitem.from_dict(**{
               "label": items.capitalize(),
               "art": art,
               "callback": search_listing,
               "params": {
                   "items": items,
               }
           })
    return

@Route.register
def featured_prog(plugin, id=None):
    for each in getFeatured():
        if id:
             if int(each.get("id", 0)) == int(id):
                data = each.get("data", [])
                for child in data:
                    art["thumb"] = art["icon"] = art["fanart"] = IMG_POSTER + child.get("episodePoster")
                    showname = html.unescape(child.get("showname"))
                    info_dict = {
                        "art": art,
                        "info": {
                            'originaltitle': showname,
                            "tvshowtitle": "Featured",
                            "genre": child.get("showGenre"),
                            "plot": child.get("description"),
                            "episodeguide": child.get("episode_desc"),
                            "episode": 0 if child.get("episode_num") == -1 else child.get("episode_num"),
                            "cast": child.get("starCast", "").split(', '),
                            "director": child.get("director"),
                            "duration": child.get("duration")*60,
                            "tag": child.get("keywords"),
                            "mediatype": "movie" if child.get("channel_category_name") == "Movies" else "episode",
                        }
                    }
                    if child.get("showStatus") == "Now":
                        info_dict["label"] = info_dict["info"]["title"] = showname + " - " + child.get("channel_name") + Livetext
                        info_dict["callback"] = play
                        info_dict["params"] = {
                            "channel_id": child.get("channel_id")}
                        yield Listitem.from_dict(**info_dict)
                    elif child.get("showStatus") == "future":
                        timetext = returnDT(each, "startEpoch", dtftsStart) + returnDT(each, "endEpoch", dtftsEnd)
                        info_dict["label"] = info_dict["info"]["title"] = showname + " - " + child.get("channel_name") + ("[COLOR lime]%s[/COLOR]" % timetext)
                        info_dict["callback"] = ""
                        yield Listitem.from_dict(**info_dict)
                    elif child.get("showStatus") == "catchup":
                        timetext = returnDT(each, "startEpoch", dtftsStart) + returnDT(each, "endEpoch", dtftsEnd)
                        info_dict["label"] = info_dict["info"]["title"] = showname + " - " + child.get("channel_name") + ("[COLOR yellow]%s[/COLOR]" % timetext)
                        info_dict["callback"] = play
                        info_dict["params"] = {
                            "channel_id": child.get("channel_id"),
                            "showtime": child.get("showtime", "").replace(":", ""),
                            "srno": returnDT(each, "startEpoch", '%Y%m%d'),
                            "programId": child.get("srno", ""),
                            "begin": returnDT(each, "startEpoch", dtfts, True),
                            "end": returnDT(each, "endEpoch", dtfts, True)
                        }
                        yield Listitem.from_dict(**info_dict)

@Route.register
def show_featured(plugin, id=None):
    tabsKeys = list(tabsDict.keys())
    for tabid in tabsKeys:
        yield Listitem.from_dict(**{
                "label": tabsDict[tabid],
                "art": art,
                "callback": Route.ref(mpath + "tabs_cat"),
                "params": {"tabid": tabid}
               })
    for each in getFeatured():
        if id:
             if int(each.get("id", 0)) == int(id):
                data = each.get("data", [])
        else:
            yield Listitem.from_dict(**{
                "label": each.get("name"),
                "art": art,
                "callback": featured_prog,
                "params": {"id": each.get("id")}
            })

@Script.register
def guidepop(plugin, ptitle, pdesc):
    Dialog().ok(ptitle, pdesc)

@Script.register
def programInfo(plugin, srno):
    pData = getChData(srno)
    showtime = datetime.fromtimestamp(int(pData["startEpoch"]*.001)).strftime(progDT)
    Cast = "[CR]Cast: " + pData["starCast"] if pData["starCast"] != "" else ""
    Description = ""
    if pData["description"] != "":
        Description = pData["description"]
    elif pData["episode_desc"] != "":
        Description = pData["episode_desc"]
    ptitle = str(pData["showname"]) + ("" if pData['episode_num'] == -1 else ", Ep." + str(pData['episode_num']))
    pdesc = str("[B]" + pData["channel_name"] + "[/B]" + showtime + Cast + "[CR][CR]" + Description)
    Dialog().ok(ptitle, pdesc)

@Route.register
def past_progs_ep(plugin, channel_show_id, isEpisode=False):
    resp = urlquick.get(PAST_PROGS_EPISODES.format(channel_show_id), verify=False, headers=uaheaders, max_age=-1).json()
    epgpastData = resp['pastData'] if isEpisode else resp['epg']
    for each in epgpastData:
        showname = html.unescape(each['showname'])
        if isEpisode and each['episode_num'] != -1:
            showname += ", Ep." + str(each['episode_num'])
        showname = "[COLOR yellow]%s[/COLOR]" % showname
        showdt = returnDT(each, "startEpoch", progDT)
        showlabel = " | ".join([showname, showdt])
        beginStr = returnDT(each, "startEpoch", dtfts, True)
        endStr = returnDT(each, "endEpoch", dtfts, True)
        showId = each.get("showId", "")
        srno = each.get("srno", "")
        art["thumb"] = art["icon"] = art["fanart"] = IMG_POSTER + each['episodePoster']
        listpastprogs = Listitem.from_dict(**{
            "label": showlabel,
            "art": art,
            "callback": play,
            "info": {
                'title': showlabel,
                'originaltitle': showname,
                "tvshowtitle": pastprog[:-1],
                'genre': each['showGenre'],
                'plot': each['description'],
                "episodeguide": each.get("episode_desc"),
                'episode': 0 if each['episode_num'] == -1 else each['episode_num'],
                'cast': each['starCast'].split(', '),
                'director': each['director'],
                'duration': each['duration']*60,
            },
            "params": {
                "channel_id": each.get("channel_id"),
                "showtime": each.get("showtime", "").replace(":", ""),
                "srno":  returnDT(each, "startEpoch", '%Y%m%d'),
                "programId": each.get("srno", ""),
                "begin": beginStr,
                "end": endStr,
            }
        })
        if hasCatchup(each): 
            if not isEpisode and each.get("episode_num") != -1:
                contextMenu(listpastprogs, past_progs_ep, pastepis, showId, True)
        listpastprogs.context.container(programInfo, prginfo, srno)
        yield listpastprogs

@Route.register
def show_epgtvg(plugin, day, channel_id, epgmode=True): 
    resp = urlquick.get(CATCHUP_SRC.format(day, channel_id), verify=False, headers=uaheaders, max_age=-1).json()
    epg = sorted(
        resp['epg'], key=lambda show: show['startEpoch'], reverse=epgmode)
    for each in epg:
        current_epoch = int(time()*1000)
        islive = each['startEpoch'] < current_epoch and each['endEpoch'] > current_epoch
        isfut = each['startEpoch'] > current_epoch
        islivorfut = islive or isfut
        if isfut and epgmode:
            continue
        if not islivorfut and not epgmode:
            continue
        showname = html.unescape(each['showname'])
        showdt = returnDT(each, "startEpoch", dtftsStart) + returnDT(each, "endEpoch", dtftsEnd)
        showtiming = Livetext + "[COLOR red]%s[/COLOR]" % showdt if islive else showdt
        showtiming = "[COLOR yellow]%s[/COLOR]" % showtiming if not islive and epgmode else "[COLOR lime]%s[/COLOR]" % showtiming
        beginStr = returnDT(each, "startEpoch", dtfts, True),
        endStr = returnDT(each, "endEpoch", dtfts, True),
        showId = each.get("showId", "")
        srno = each.get("srno", "")
        art["thumb"] = art["icon"] = art["fanart"] = IMG_POSTER + each['episodePoster']
        listprogs = Listitem.from_dict(**{
            "label": showname + showtiming,
            "art": art,
            "callback": play if islive or not isfut else guidepop,
            "info": {
                'title': showname + showtiming,
                'originaltitle': showname,
                "tvshowtitle": Livetext if islive else Ctchp,
                'genre': each['showGenre'],
                'plot': each['description'],
                "episodeguide": each.get("episode_desc"),
                'episode': 0 if each['episode_num'] == -1 else each['episode_num'],
                'cast': each['starCast'].split(', '),
                'director': each['director'],
                'duration': each['duration']*60,
                'tag': each['keywords'],
                'mediatype': 'episode',
            },
            "params": {
                "channel_id": each.get("channel_id"),
                "showtime": None if islive else each.get("showtime", "").replace(":", ""),
                "srno": None if islive else returnDT(each, "startEpoch", '%Y%m%d'),
                "programId": None if islive else each.get("srno", ""),
                "begin": None if islive else beginStr,
                "end": None if islive else endStr,
            } if islive or not isfut else {
                "ptitle": showname + ("" if each['episode_num'] == -1 else ", Ep." + str(each['episode_num'])),
                "pdesc": "[B]" + showtiming + ", " + each['channel_name'] + "[/B][CR]" + ("" if each['starCast'] == "" else "Cast: " + each['starCast']) + "[CR]" + each['description'],
            }
        })
        if hasCatchup(each) and each.get("stbCatchupAvailable"):
            contextMenu(listprogs, past_progs_ep, pastepis, showId, True)
        listprogs.context.container(programInfo, prginfo, srno)
        yield listprogs
    if int(day) == 0:
        grange = range(-1, -7, -1) if epgmode else range(1, 8, 1)
        for i in grange:
            tday = {-1: "Yesterday", 0: "Today", 1: "Tomorrow"}
            iCond = (i > -2) if epgmode else (i < 2)
            dayt = ", " + tday[i] if iCond else ""
            daylabel = "[B]" + (date.today() + timedelta(days=i)).strftime('%a, %d %b %Y') + "[/B]" + dayt
            art["thumb"] = art["icon"] = art["fanart"] = IMG + resp["logoUrl"]
            yield Listitem.from_dict(**{
                "label": daylabel,
                "art": art,
                "info": {
                "title": daylabel,
                           },
                "callback": show_epgtvg,
                "params": {
                    "day": i,
                    "channel_id": channel_id,
                    "epgmode": epgmode
                }
            })

@isLoggedIn
def checkLogin():
    if not getBool("isloggedin"):
        sys.exit()

@Resolver.register
def play(plugin, channel_id, showtime=None, srno=None, programId=None, begin=None, end=None):
    drm = "com.widevine.alpha"
    selectionType = GSET("sstype").lower()    
    resMax = GSET("resmax")    
    resSecMax = GSET("ressecmax")
    props = {
       "IsPlayable": True,
       "inputstream": IID,
       "inputstream.adaptive.stream_selection_type": selectionType,
       "inputstream.adaptive.chooser_resolution_max": resMax,
       "inputstream.adaptive.chooser_resolution_secure_max": resSecMax,
           }
    isCatchup = False
    playLabel = ""
    ch_logo = ""
    if int(channel_id) < 4000:
        epgresp = urlquick.get(CATCHUP_SRC.format(0, channel_id), verify=False, headers=uaheaders, max_age=-1).json()    
        epg = sorted(epgresp['epg'], key=lambda show: show['startEpoch'], reverse=False)    
        for each in epg:
            current_epoch = int(time()*1000)        
            islive = each['startEpoch'] < current_epoch and each['endEpoch'] > current_epoch        
            if islive:
               showname = html.unescape(each['showname'])
               showdt = returnDT(each, "startEpoch", dtftsStart) + returnDT(each, "endEpoch", dtftsEnd)
               playLabel += " • ".join([showname, showdt])
        ch_logo = epgresp['logoUrl']
    uriToUse = ""
    qltyopt = GSET("quality")
    manifestHeaders = "User-Agent=Mozilla%2F5.0"
    licenseKey = "|" + manifestHeaders + "||"
    props.update({
    "inputstream.adaptive.stream_headers": manifestHeaders,
    "inputstream.adaptive.manifest_headers": manifestHeaders,
    "inputstream.adaptive.license_key": licenseKey,
        })
    isIntCh = int(channel_id) in intUrls
    if isIntCh and getBool("redextch"):
        channel_id = int(channel_id)
        uriToUse = intRdr(channel_id)
        art["thumb"] = art["icon"] = art["fanart"] = ch_logo
        return Listitem().from_dict(**{
        "label": plugin._title,
        "info": {
                "title": playLabel,
                "tvshowtitle": Livetext,
                "originaltitle": playLabel,                            
                "tvshowtitle": playLabel,
                },
        "art": art,
        "callback": uriToUse,
        "properties": props
    })
    checkLogin()
    if not getBool("isloggedin"):
        sys.exit()
    is_helper = inputstreamhelper.Helper("mpd", drm)
    if not is_helper.check_inputstream():
        return    
    rqbody = {
    "stream_type": "Seek",
    "channel_id": int(channel_id)
    }
    if showtime and srno:
        isCatchup = True
        rqbody["stream_type"] = "Catchup"
        rqbody["showtime"] = showtime
        rqbody["srno"] = srno
        rqbody["programId"] = programId
        rqbody["begin"] = begin
        rqbody["end"] = end
    headers = getHeaders()
    headers['channelid'] = str(channel_id)
    headers['srno'] = dtnow.strftime('%y%m%d%H%M%S') if "srno" not in rqbody else rqbody["srno"]

    v1headers = {  
    "accept-encoding": "gzip",                  
    "accesstoken": headers["authtoken"] if getBool("isloggedin") else "",                    
    "appkey": appkey,
    "channel_id": str(channel_id),
    "dm": dm,
    "isott": "false",
    "langid": "",                                                          
    "languageid": "6",
    "lbcookie": "1",                              
    "subscriberid": headers["subscriberid"],
    "user-agent": httpuseragent,
    "usergroup": usergroup,
    "userId": headers["userid"],
    "uniqueId": headers["uniqueid"],
    "crmid": headers["crmid"],
    "usergroup": usergroup,
    "deviceId": headers["deviceid"],
    "devicetype": devicetype,
    "os": oprsys,
    "osversion": osver,
    "versioncode": vercode,
    }
    isTimesPlay = int(channel_id) in [151, 462, 477, 478, 877, 1401]
    isHlsPartner = int(channel_id) in [532, 584, 736, 1066, 1920, 2183, 2955, 3054, 3055, 3074, 3075, 3156, 3157, 3158, 3159]
    needsPbapiv1 = isHlsPartner or isTimesPlay
    chHeaders = v1headers if isPbapiv1 or needsPbapiv1 else getChannelHeaders()
    playbackUrl = PBV1URL if isPbapiv1 or needsPbapiv1 else GET_CHANNEL_URL
    resp = (urlquick.post(playbackUrl, data=rqbody, verify=False, headers=chHeaders, max_age=-1, raise_for_status=True)).json()
    if isPbapiv1 and resp.get("code") == 419:
        executebuiltin(runPgRefresh + "token/)")
        executebuiltin(runPgMain + "play/?channel_id={0})".format(str(channel_id)))
        return
    onlyUrl = resp.get("result", "").split("?")[0].split('/')[-1]
    art["thumb"] = art["icon"] = art["fanart"] = IMG + onlyUrl.replace(".m3u8", ".png")
    cookie = "__hdnea__"+resp.get("result", "").split("__hdnea__")[-1]
    headers['cookie'] = cookie
    uriToUse = resp.get("result", "")
    mpdArray = resp.get("mpd")
    isMPD = getBool("usempd")
    mpdMode = isMPD and mpdArray
    if mpdMode or isTimesPlay:
        uriToUse = mpdArray.get("result", "")
        drmKey = mpdArray.get("key")   
        license_headers = {
                "ssoToken": headers.get("ssotoken"),
                "channelid": str(channel_id),
                "content-type": "application/octet-stream",
                "deviceId": headers.get("deviceid"),
                "devicetype": devicetype,
                "os": oprsys,
                "osversion": osver,
                "srno": srno,
                "uniqueId": headers.get("uniqueid"),
                "user-agent": useragent,
                "usergroup": usergroup,
                "versioncode": vercode,
            }            
        if isPbapiv1:        
             license_headers.update({"accesstoken": headers.get("authtoken")})
        manifestHeaders = urlencode(license_headers)
        licenseKey = drmKey + "|" + manifestHeaders
    else:
        m3u8Headers = {}
        m3u8Headers['user-agent'] = GSET("useragent")
        m3u8Headers['cookie'] = cookie
        if isPbapiv1:        
             m3u8Headers.update({"accesstoken": headers.get("authtoken")})
        m3u8Res = urlquick.get(uriToUse, headers=m3u8Headers, verify=False, max_age=-1, raise_for_status=True)
        m3u8String = m3u8Res.text
        variant_m3u8 = m3u8.loads(m3u8String)
        isVariant = variant_m3u8.is_variant
        if GSET("sstype") == "Adaptive" and isVariant:
            playlistLength = len(variant_m3u8.playlists)
            quality = quality_to_enum(qltyopt, playlistLength)
            uriToUse = uriToUse.replace(onlyUrl, variant_m3u8.playlists[quality].uri)
            if isCatchup:
                splitUri = uriToUse.split("?")
                uriToUse = "?".join([splitUri[0], splitUri[2]])
                del headers['cookie']
        manifestHeaders = urlencode(headers)
        licenseKey = "|" + urlencode(headers)
    props.update({
    "inputstream.adaptive.license_type": drm,
    "inputstream.adaptive.license_key": licenseKey + "|R{SSM}|R",
        })
    return Listitem().from_dict(**{
        "label": playLabel if not isCatchup else plugin._title,
        "info": {
                "title": playLabel if not isCatchup else plugin._title,
                "tvshowtitle": playLabel if not isCatchup else plugin._title, # '[COLOR yellow]%s[/COLOR]' % Ctchp if isCatchup else Livetext,                            
                "originaltitle": playLabel if not isCatchup else plugin._title,                            
                "tvshowtitle": playLabel if not isCatchup else plugin._title,
                },
        "art": art,
        "callback": uriToUse,
        "properties": props
    })

@Script.register
def m3ugen(plugin, notify="yes"):
    PLAY_URL = runPgMain[10:] + "play/?"
    M3U_CHANNEL = "\n#EXTINF:0 tvg-id=\"{tvg_id}\" tvg-name=\"{channel_name}\" group-title=\"{group_title}\" tvg-chno=\"{tvg_chno}\" tvg-logo=\"{tvg_logo}\"{catchup},{channel_name}\n{play_url}"
    m3ustr = "#EXTM3U"
    m3ustr += " x-tvg-url=\"%s\"" % EPG_DATA        
    for i, channel in enumerate(channels):
        Lan, Cat = mapId(channel)
        if getBool("filterplaylist"):
            if not getBool(Lan):
               continue 
            if not getBool(Cat):
               continue
        isHD = channel.get("isHD")
        if hdsdch == 1 and not isHD:
            continue
        if hdsdch == 2 and isHD:
            continue
        channel_id = channel.get("channel_id")
        channel_logo = chlogo(channel)
        group = Lan + ";" + Cat
        _play_url = PLAY_URL + "channel_id={0}".format(channel_id)
        catchup = ""
        if channel.get("isCatchupAvailable"):
            catchup = ' catchup="vod" catchup-source="{0}channel_id={1}&showtime={{H}}{{M}}{{S}}&srno={{catchup-id}}&programId={{catchup-id}}&begin=${{start}}&end=${{end}}" catchup-days="7"'.format(PLAY_URL, channel_id)
        m3ustr += M3U_CHANNEL.format(
            tvg_id=channel_id,
            channel_name=channel.get("channel_name"),
            group_title=group,
            tvg_chno=int(channel.get("channel_order", i)) + 1,
            tvg_logo=channel_logo,
            catchup=catchup,
            play_url=_play_url,
        )
    with open(M3U_SRC, "w+") as f:
        f.write(m3ustr.replace(u'\xa0', ' ').encode('utf-8').decode('utf-8'))
    urlquick.cache_cleanup(-1)
    if notify == "yes":
        notif("Playlist Updated. Restart")

@Script.register 
def open_settings(plugin, id):
    Addon(id).openSettings()

@Route.register
def show_settings(plugin):
    def lab(id):
       Ai = Addon(id).getAddonInfo
       return str(Ai("name") + " " + list(menu.values())[menuLen-1])
    for id in [AID, PID, IID]:
        hasAddonInstalled = xbmc.getCondVisibility('System.HasAddon(%s)' % id)
        isAddonEnabled = xbmc.getCondVisibility('System.AddonIsEnabled(%s)' % id)
        if hasAddonInstalled and isAddonEnabled:
            yield Listitem.from_dict(**{
               "label": lab(id),
               "art": art,
               "callback": open_settings,
               "params": {"id": id}
           })

@Script.register
def pvrsetup(plugin):
    modeEpg = Dialog().yesnocustom(ANM + " EPG Mode", "[B]Select EPG Mode for %s : [/B][CR]  Auto generates EPG once now and then daily at set time.[CR]  Manual generates EPG once now only.[CR]  Online EPG will use URL for it. For [B]No EPG[/B] close this dialog or click outside this dialog." % ANM, yeslabel="Auto EPG", nolabel="Manual EPG", customlabel="Online EPG", defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
    if modeEpg == 1:
        autoEpgTime = Dialog().input("Enter Auto-EPG Daily Time [CR] (24 hours HH:MM format)", defaultt="08:00", type=xbmcgui.INPUT_TIME)
        SSET("genepg", "true")
        SSET("genepgtime", autoEpgTime)
        executebuiltin(runPg + "utils/epg/)")
    elif modeEpg == 0:
        SSET("genepg", "false")
        executebuiltin(runPg + "utils/epg/)")
    elif modeEpg == 2:
        SSET("genepg", "false")
        urlEpg = Dialog().input("Enter Online EPG URL/Link", type=xbmcgui.INPUT_ALPHANUM)
        SSET("epg_url", urlEpg)
    else:
        SSET("genepg", "false")
    EPG_PATH_TYP = "1" if modeEpg == 2 and onlineEPG else "0"
    executebuiltin(runPgMain + "m3ugen/?notify=no)")
    def set_setting(id, value):
        if Addon(PID).getSetting(id) != value:
            Addon(PID).setSetting(id, value)
    if check_addon(PID):
        set_setting("m3uPathType", "0")
        set_setting("m3uPath", M3U_SRC)
        set_setting("epgPathType", EPG_PATH_TYP)
        set_setting("epgUrl" if onlineEPG else "epgPath", EPG_DATA)
        set_setting("catchupEnabled", "true")
        set_setting("catchupWatchEpgBeginBufferMins", "0")
        set_setting("catchupWatchEpgEndBufferMins", "0")
    _setup(M3U_SRC, EPG_DATA)

@Script.register
def cleanup(plugin):
    urlquick.cache_cleanup(-1)
    cleanLocalCache()
    notif("Cache cleared")

@Script.register
def login(plugin):
    if GSET("mobile") != "":
        intmobile = GSET("mobile")
        mobile = str(intmobile)
    else:
        mobile = Dialog().numeric(0, "Enter " + ANM[:-2] + " number")
        SSET("mobile", mobile)
    error = sendOTP(mobile)
    if error:
        notif("Login Error " + error)
        return
    otp = Dialog().numeric(0, "Enter " + ANM + " OTP")
    ULogin(mobile, otp)

@Script.register
def logout(plugin):
    logoutyn = Dialog().yesno(ANM + " Logout", "Logout from %s?" % ANM, yeslabel="Yes", nolabel="No")
    if logoutyn == 1:
        urlquick.cache_cleanup(-1)
        ULogout()            
    else:             
        return
