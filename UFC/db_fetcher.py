#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
#import pandas as pd
import re
import mysql.connector
import MySQLdb.cursors

rx = re.compile(u'[\W]+', re.UNICODE)

mydb = mysql.connector.connect(host="localhost", user="andrelo", password="", database="ufc")
mycursor = mydb.cursor()

def get_fighter_id(element):
    nameW = name_cleaner(element.text)
    mycursor.execute('SELECT fighter_id FROM fighters WHERE name = "%s";'%(nameW))
    result = mycursor.fetchall()
    if len(result):
        fighter_id, = result[0]
    else:
        link = element.find('a')
        if type(link) != type(None):
            f_wiki = link['href'].replace('/wiki/', '')
            mycursor.execute("SELECT fighter_id FROM fighters WHERE wiki_link = '%s';"%(f_wiki))
            result = mycursor.fetchall()
            if len(result):
                fighter_id, = result[0]
            else:
                fighter_id = 0
        else:
            fighter_id = 0
    return fighter_id

def size_text_fix(text):
    for parts in text.split('('):
        if not "in" in parts:
            return re.sub(r'\D', '', parts)

def name_cleaner(text):
    return re.sub('\(.+\)', '', text).replace('’','\'').strip()

def get_fighter_info(name, wiki):
    if wiki == '':
        sql = "INSERT INTO fighters (name) VALUES (%s)"
        mycursor.execute(sql,[name])
        mydb.commit()
    else:
        page = requests.get("https://en.wikipedia.org/wiki/%s"%(wiki))
        if page.status_code == 200:
            print('Getting data for %s.'%(name))
            fsoup = BeautifulSoup(page.content, 'html.parser')
            page.close()
            finfo = fsoup.findAll('table', attrs={'class':'infobox vcard'})[-1].find('tbody')
            try:
                b_date = finfo.find('span', attrs={'class':'bday'}).text
            except:
                b_date = '0000-01-01'
            try:
                ttext = finfo.find('th', string="Height").parent()[1].text
                height = size_text_fix(ttext)
            except:
                height = '0'
            try:
                ttext = finfo.find('th', string="Reach").parent()[1].text
                reach = size_text_fix(ttext)
            except:
                reach = '0'
            try:
                out_of = finfo.find('th', string="Fighting out of").parent()[1].text
                out_of = out_of[:60] if len(out_of) > 60 else method
            except:
                out_of = 'Unknown'
            try:
                team = re.sub(' +', ' ', re.sub(r'\((.*?)\)', '', re.sub('\[.\]', ' ', finfo.find('th', string="Team").parent()[1].text))).strip()
                team = team[:100] if len(team) > 100 else team
            except:
                team = ""
            try:
                active = finfo.find('th', string="Years active").parent()[1].text.replace(' ','')[:9].split('–')
                active_since = active[0]
                active_till = active[1].replace('pres','0000')
            except:
                active_since = '0000'
                active_till = '0000'

            sql = "INSERT INTO fighters (name, b_date, height, reach, out_of, team, active_since, active_till, wiki_link) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            mycursor.execute(sql,(name, b_date, height, reach, out_of, team, active_since, active_till, wiki))

            mydb.commit()
        else:
            print("Failed to get the page https://en.wikipedia.org/wiki/%s"%(wiki))

def get_fight_info(event_id, full_page):
    w_classes = {'Heavyweight': 'hw', 'Light Heavyweight': 'lh', 'Middleweight': 'mw', 'Welterweight': 'ww', 'Lightweight': 'lw', 'Featherweight': 'fw', 'Bantamweight': 'bw', 'Flyweight': 'fw', "Women's Strawweight": 'ws', "Women's Flyweight": 'wf', "Women's Bantamweight": 'wb', "Women's Featherweight": 'we'}
    fight_table= full_page.find('table', attrs={'class':'toccolours'}).find('tbody')

    print("Now adding fights.")
    fight_list = list()
    for fight in fight_table.find_all('tr')[2:]:
        infos = fight.find_all('td')
        if len(infos) > 1:
            if 'atchweight' in infos[0].text or infos[0].text.strip() == 'N/A':
                w_class = "cw"
            else:
                try:
                    w_class = w_classes[infos[0].text.strip().replace('’','\'')]
                except:
                    w_class = input("Weghtclass %s not found. What is the correct class?"%(infos[0].text.strip()))
            winner = get_fighter_id(infos[1])
            loser = get_fighter_id(infos[3])
            # 0 means that fighter id was not found and fight should not be added
            if winner and loser:
                method = infos[4].text
                method = re.sub(rx, ' ', method).strip()

                method = method[:50] if len(method) > 50 else method
                try:
                    parts = infos[6].text.split(':')
                    time = 60*int(parts[0]) + int(parts[1])
                    Round = int(infos[5].text)
                except:
                    time = 0
                    Round = 0

                ref = infos[7].find('a')
                if ref != None:
                    ref_id = ref['href'].replace('#' , '')
                    ref_element = full_page.find(id=ref_id)
                    if ref_element != None:
                        notes = ref_element.text
                        notes = re.sub(rx, ' ', notes)
                        notes = notes[:60] if len(notes) > 60 else notes
                    else:
                        notes = ""
                else:
                    notes = ""
                event_id = event_id
                fight_list.append((w_class, winner, loser, method, time, Round, notes, event_id))

    sql = "INSERT INTO fights (w_class, winner, loser, method, time, round, notes, event_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    mycursor.executemany(sql, fight_list)
    mydb.commit()

def check_fighters(event_id, e_wiki):
    mycursor.execute("SELECT name FROM fighters;")
    fighter_list = list(map(lambda x: x[0], mycursor.fetchall()))
    print("Got fighters names.")
    mycursor.execute("SELECT wiki_link FROM fighters;")
    fwikis = list(map(lambda x: x[0], mycursor.fetchall()))

    page = requests.get("https://en.wikipedia.org/wiki/%s"%(e_wiki))
    if page.status_code == 200:
        print("Got event page.")
        soup = BeautifulSoup(page.content, 'html.parser')
        page.close()
        table = soup.find('table', attrs={'class':'toccolours'}).find('tbody')
        for fight in table.find_all('tr')[2:]:
            infos = fight.find_all('td')
            if len(infos) > 1:
                nameW = name_cleaner(infos[1].text)
                if not nameW in fighter_list:
                    print("Fighter %s not in fighter list."%(nameW))
                    try:
                        f_wiki = table.find('a',string=nameW)['href'].replace('/wiki/', '')
                        if not f_wiki in fwikis:
                            get_fighter_info(nameW, f_wiki)
                    except:
                        get_fighter_info(nameW, '')

                nameL = name_cleaner(infos[3].text)
                if not nameL in fighter_list:
                    print("Fighter %s not in fighter list."%(nameL))
                    try:
                        f_wiki = table.find('a',string=nameL)['href'].replace('/wiki/', '')
                        if not f_wiki in fwikis:
                            get_fighter_info(nameW, f_wiki)
                    except:
                        get_fighter_info(nameW, '')
        get_fight_info(event_id, soup)

mycursor.execute("SELECT event_id,wiki_link FROM occurance;")
events = mycursor.fetchall()
events.reverse()

mycursor.execute("SELECT DISTINCT event_id FROM fights;")
logged_events = list(map(lambda x: x[0], mycursor.fetchall()))


for event_id,event_wiki in events:
    if (not 'index' in event_wiki) and (not event_id in logged_events):
        print(event_wiki)
        check_fighters(event_id, event_wiki)


#check_fighters(1961, "UFC_274")
