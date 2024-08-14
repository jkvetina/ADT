# coding: utf-8
import sys, os, argparse, datetime
#
from config     import Config
from patch      import Patch
import lib.util as util

#
#                                                      (R)
#                      ---                  ---
#                    #@@@@@@              &@@@@@@
#                    @@@@@@@@     .@      @@@@@@@@
#          -----      @@@@@@    @@@@@@,   @@@@@@@      -----
#       &@@@@@@@@@@@    @@@   &@@@@@@@@@.  @@@@   .@@@@@@@@@@@#
#           @@@@@@@@@@@   @  @@@@@@@@@@@@@  @   @@@@@@@@@@@
#             \@@@@@@@@@@   @@@@@@@@@@@@@@@   @@@@@@@@@@
#               @@@@@@@@@   @@@@@@@@@@@@@@@  &@@@@@@@@
#                 @@@@@@@(  @@@@@@@@@@@@@@@  @@@@@@@@
#                  @@@@@@(  @@@@@@@@@@@@@@,  @@@@@@@
#                  .@@@@@,   @@@@@@@@@@@@@   @@@@@@
#                   @@@@@@  *@@@@@@@@@@@@@   @@@@@@
#                   @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@.
#                    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@
#                    @@@@@@@@@@@@@@@@@@@@@@@@@@@@
#                     .@@@@@@@@@@@@@@@@@@@@@@@@@
#                       .@@@@@@@@@@@@@@@@@@@@@
#                            jankvetina.cz
#                               -------
#
# Copyright (c) Jan Kvetina, 2024
# https://github.com/jkvetina/ADT
#

class Calendar(Patch, Config):

    def define_parser(self):
        parser = argparse.ArgumentParser(add_help = False)

        # actions and flags
        group = parser.add_argument_group('MAIN ACTIONS')
        group.add_argument('-calendar',     help = 'Show commits/tickets in a calendar',        type = util.is_boolint, nargs = '?', const = True,  default = False)
        group.add_argument('-list',         help = 'Show commits as a list for a report',       type = util.is_boolint, nargs = '?', const = True,  default = False)
        #
        group = parser.add_argument_group('LIMIT SCOPE')
        group.add_argument('-my',           help = 'Show only my commits',                                              nargs = '?', const = True,  default = False)
        group.add_argument('-by',           help = 'Show commits by specific author',                                   nargs = '?')
        #
        return parser



    def __init__(self, parser = None, args = None):
        self.parser = parser or self.define_parser()
        super().__init__(parser = self.parser, args = args)

        # show commits/tickets for each team mamber and current/offset week
        self.show_calendar(offset = self.args.calendar)
        util.beep_success()



    def show_calendar(self, offset = 0):
        if offset and isinstance(offset, bool):
            offset = 0
        #
        today           = datetime.datetime.today().replace(hour = 0, minute = 0, second = 0, microsecond = 0)
        first_day       = datetime.datetime.today().replace(day = 28)
        if offset > 0:
            first_day   -= datetime.timedelta(days = offset * 30)       # will work fine for past few years
        first_day       = first_day.replace(day = 1)
        #
        first_monday    = first_day - datetime.timedelta(days = first_day.weekday())
        year_month      = first_day.strftime('%Y-%m')

        # get calendar data
        self.commits_daily   = {}
        self.commits_tickets = {}
        #
        self.get_calendar_data(year_month)

        # show monthly overview
        authored = {}
        for commit_num, info in self.all_commits.items():
            if info['date'].strftime('%Y-%m') == year_month:
                author = self.get_author(info['author'])
                if not (author in authored):
                    authored[author] = []
                authored[author].append(commit_num)
        #
        util.print_header('MONTHLY OVERVIEW:', year_month)
        for author in sorted(authored.keys()):
            if author in self.commits_tickets:
                util.print_dots('  ' + author, right = len(authored[author]), width = 49)
        print()

        # for each author with some commits
        for author in sorted(self.commits_tickets.keys()):
            count_commits   = len(self.commits_tickets[author])
            count_tickets   = len(set(self.commits_tickets[author]))
            #
            if not count_tickets:
                continue

            # show header
            if not self.args.my:
                print('\n' + '-' * 80)
            util.print_header('{} COMMITS BY {} ({})'.format(count_commits, author, count_tickets))

            # show monthly calendar
            author_commits = {}
            for week in range(0, 6):        # max 6 weeks in a month
                curr_date = first_monday + datetime.timedelta(days = week * 7)
                days, no_headers = [], []
                #
                for day in range(0, 7):     # max 7 days in a week
                    curr_month  = curr_date.strftime('%Y-%m') == year_month
                    header      = curr_date.strftime('%Y-%m-%d')
                    if not curr_month:
                        header  = ' ' * (day + 1)
                        no_headers.append(day)      # to get rid of the splitter
                    #
                    curr_date += datetime.timedelta(days = 1)
                    if day >= 5:
                        continue            # show just 5 days (Mon-Fri)
                    days.append(header)
                #
                if len(''.join(days).strip()) > 0:
                    # get commits/tickets for each day
                    for i, day in enumerate(days, start = 1):
                        if not (day in author_commits):
                            author_commits[day] = []
                        author_commits[day].extend(self.commits_daily.get(day, {}).get(author, {}).keys() or [''])

                    # calculate number of rows, fix dupes
                    max_commits = 0
                    for date in days:
                        max_commits = max(max_commits, len(author_commits[date]))
                        author_commits[date] = sorted(set(author_commits[date]))

                    # pivot data
                    data = []
                    for line in range(max_commits):
                        row = {}
                        for date in days:
                            #if date == today.strftime('%Y-%m-%d') and not ('^' in author_commits[date]):
                            #    author_commits[date].append('^')
                            row[date] = author_commits[date][line] if len(author_commits[date]) - 1 >= line else ''
                        data.append(row)

                    if self.args.calendar:
                        util.print_table(data, columns = dict(zip(days, [12] * 5)), no_header = no_headers)
                        print()

            # show as list
            if self.args.list:
                print()
                for week in range(0, 6):        # max 6 weeks in a month
                    curr_date = first_monday + datetime.timedelta(days = week * 7)
                    #
                    for day in range(0, 7):     # max 7 days in a week
                        curr_month  = curr_date.strftime('%Y-%m') == year_month
                        date        = curr_date.strftime('%Y-%m-%d')
                        curr_date   += datetime.timedelta(days = 1)
                        #
                        if curr_month:
                            print(date, ', '.join(author_commits.get(date, [])))
                    print()
                print()



    def get_calendar_data(self, year_month):
        for commit_num in self.filtered_commits:
            info = self.all_commits[commit_num]
            if not ('ticket' in info):
                continue

            # move weekend work to previous Friday
            weekday = info['date'].weekday() + 1
            if weekday == 6:
                info['date'] -= datetime.timedelta(days = 1)
            elif weekday == 7:
                info['date'] -= datetime.timedelta(days = 2)

            # get info info
            ticket  = info.get('ticket', '')
            author  = self.get_author(info['author'])
            date    = info['date'].strftime('%Y-%m-%d')

            # process requested month only
            if info['date'].strftime('%Y-%m') != year_month:
                continue

            # gather some stats
            if not (author in self.commits_tickets):
                self.commits_tickets[author] = []
            self.commits_tickets[author].append(ticket)

            # sort commits
            if not (date in self.commits_daily):
                self.commits_daily[date] = {}
            if not (author in self.commits_daily[date]):
                self.commits_daily[date][author] = {}
            if not (ticket in self.commits_daily[date][author]):
                self.commits_daily[date][author][ticket] = []
            #
            self.commits_daily[date][author][ticket].append(commit_num)



if __name__ == "__main__":
    Calendar()

