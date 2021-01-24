#!/usr/bin/env python -OO
# -*- coding: utf-8 -*-

from __future__ import with_statement
from bs4 import BeautifulSoup
from glob import glob

import os
import re
import pymongo
import sys

def main():
    """Loop thru all the games and parse them."""
    DIR = "j-archive"
    if not os.path.isdir(DIR):
        print "The specified folder is not a directory."
        sys.exit(1)
    NUMBER_OF_FILES = len(os.listdir(DIR))
    print "Parsing", NUMBER_OF_FILES, "files"
    mongoClient = pymongo.MongoClient("mongodb://localhost:27017/")
    clueDB = mongoClient["jeopardy"]
    clueCol = clueDB["clues"]

    for i, fileName in enumerate(glob(os.path.join(DIR, "*.html")), 1):
        with open(os.path.abspath(fileName)) as f:
            parseGame(f, clueCol, i)
    print "All done"

def parseGame(f, col, gid):
    # parse entire game and extract clues
    bsoup = BeautifulSoup(f, "lxml")
    # Title is in the format: `J! Archive Show #XXXX, aired 2004-09-16`,
    # where the last part is all that is required
    airdate = bsoup.title.get_text().split()[-1]
    if not parseRound(bsoup, col, 1, gid, airdate) or not parseRound(bsoup, col, 2, gid, airdate):
        # One of the rounds doesnt exist
        pass
    # Final jeopardy round
    r = bsoup.find("table", class_="final_round")
    if not r:
        # This game doesnt have a final clue
        return
    category = r.find("td", class_="category_name").get_text()
    text = r.find("td", class_="clue_text").get_text()
    answer = BeautifulSoup(r.find("div", onmouseover=True).get("onmouseover"), "lxml")
    answer = answer.find("em").get_text()
    # False indicates no preset value for a clue
    insert(col, [gid, airdate, 3, category, False, text, answer])

def parseRound(bsoup, col, rnd, gid, airdate):
    round_id = "jeopardy_round" if rnd == 1 else "double_jeopardy_round"
    r = bsoup.find(id=round_id)
    # The game may not have all the rounds
    if not r:
        return False
    # The list of categories for this round
    categories = [c.get_text() for c in r.find_all("td", class_="category_name")]
    # The x_coord determines which category a clue is in
    # because the categories come before the clues, we will
    # have to match them up with the clues later on.
    x = 0
    for a in r.find_all("td", class_="clue"):
        is_missing = True if not a.get_text().strip() else False
        if not is_missing:
            value = a.find("td", class_=re.compile("clue_value")).get_text().lstrip("D: $")
            text = a.find("td", class_="clue_text").get_text()
            answer = BeautifulSoup(a.find("div", onmouseover=True).get("onmouseover"), "lxml")
            answer = answer.find("em", class_="correct_response").get_text()
            insert(col, [gid, airdate, rnd, categories[x], value, text, answer])
        # Always update x, even if we skip
        # a clue, as this keeps things in order. there
        # are 6 categories, so once we reach the end,
        # loop back to the beginning category.
        #
        # Using modulus is slower, e.g.:
        #
        # x += 1
        # x %= 6
        #
        x = 0 if x == 5 else x + 1
    return True

def insert(col, clue):
    # Insert the given clue into the database
    # Clue is [game, airdate, round, category, value, clue, answer]
    # Note that at this point, clue[4] is False if round is 3
    if "\\\'" in clue[6]:
        clue[6] = clue[6].replace("\\\'", "'")
    if "\\\"" in clue[6]:
        clue[6] = clue[6].replace("\\\"", "\"")
    
    clueDict = {
        "game": clue[0],
        "airdate": clue[1],
        "round": clue[2],
        "category": clue[3],
        "value": clue[4],
        "clue": clue[5],
        "answer": clue[6]
    }

    col.insert_one(clueDict)

    # A game has 3 rounds: regular jeopardy, double jeopardy, final jeopardy
    # A round has 6 categories (except round 3)
    # A category has 6 clues

    # clue item
    # {
    #   game : #,
    #   round : #,
    #   value : #,
    #   clueText : string,
    #   answer : string,
    #   airdate : string,
    #   category : string,
    # }

main()