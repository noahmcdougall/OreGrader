#!/usr/bin/env python3
import sys
sys.stdout = sys.stderr
import csv
import os.path
import cherrypy
import jinja2
import io
import atexit

## Sessions enabled ##
wsgi_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
conf = {
         '/': {
             'tools.sessions.on': True
         },
         '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': os.path.join(wsgi_dir, 'assets'),
        }
    }

## Setting up jinja2's web template stuff ##
env = jinja2.Environment(loader=jinja2.FileSystemLoader('/home/noahmcdougall/OreGrader/wsgi/static'))

if cherrypy.__version__.startswith('3.') and cherrypy.engine.state == 0:
    cherrypy.engine.start(blocking=False)
    atexit.register(cherrypy.engine.stop)

## Listing variables up here that would later be user input ##
global cutoffgrade
global mingradecutoff
# cutoffgrade = 3
# mingradecutoff = 0.5

class calculate:
    @cherrypy.expose
    def index(self):
        tmpl = env.get_template('index.html')
        return tmpl.render()

    ## Initial loading of data from csv ##
    @cherrypy.expose
    def processdata(self, myFile, mingradecutoffin, cutoffgradein):
        ## User inputs ##
        cutoffgrade = float(cutoffgradein)
        mingradecutoff = float(mingradecutoffin)

        holes = []
        datatable = []
        reader = csv.reader(myFile.file)
        next(reader)
        for row in reader:
            if row[0] not in holes:
                holes.append(row[0])
            datatable.append([row[0],float(row[1]),float(row[2]),float(row[3])])

        ## Sorts the data by hole and sets the initial parameters ##
        results = []
        problemholes = []
        for i in holes:
            inorout = "out"
            grade = 0
            gradeton = 0
            length = 0
            runlength = 0
            beginning = 0
            end = 0
            iteratornum = 0
            jplusone = 0
            jplustwo = 0

            ## Iterates through the rows only where the hole ID matches ##
            for j in range(0, len(datatable)):
                ## Unsophisticated way of getting around the iteration problem at the end of the data ##
                if j+1 > len(datatable)-1:
                    jplusone = j
                else:
                    jplusone = j+1
                if j+2 > len(datatable)-1 and j+1 == len(datatable)-1:
                    jplustwo = j+1
                elif j+1 > len(datatable)-1:
                    jplustwo = j
                else:
                    jplustwo = j+2
                print(jplustwo)

                if datatable[j][0] == i:
                    length = datatable[j][2]-datatable[j][1]
                    gobacklength = datatable[iteratornum][2]-datatable[iteratornum][1]

                    ## Quick data QC to make sure rows are all consecutive with no gaps ##
                    if datatable[j-1][0] == i and datatable[j][1] != datatable[j-1][2] and datatable[j][0] not in problemholes:
                        problemholes.append(datatable[j][0])

                    ## Condition where we start into the first run ##
                    ## First one is the case where grade is higher than min cut off ##
                    if datatable[j][3] >= mingradecutoff and ((datatable[j][3]*length)+gradeton)/(runlength + length)>=cutoffgrade:
                        grade = ((datatable[j][3]*length)+gradeton)/(runlength + length)
                        runlength = runlength + length
                        gradeton = grade * runlength
                        if inorout == "out":
                            beginning = datatable[j][1]
                            iteratornum = j-1
                            gobacklength = datatable[iteratornum][2]-datatable[iteratornum][1]
                        end = datatable[j][2]
                        inorout = "in"
                    ## If the row is below min cut off, check to see if either of the the next two rows are above before diluting the composite ##
                    elif datatable[j][3] < mingradecutoff and ((datatable[j][3]*length)+gradeton)/(runlength + length)>=cutoffgrade and inorout == "in":
                        if (datatable[jplusone][0] == i and datatable[jplusone][3] > mingradecutoff) or (datatable[jplustwo][0] == i and datatable[jplustwo][3] > mingradecutoff):
                            grade = ((datatable[j][3]*length)+gradeton)/(runlength + length)
                            runlength = runlength + length
                            gradeton = grade * runlength
                            end = datatable[j][2]
                        else:
                            results.append({'Holeid' : i, 'From' : beginning, 'To' : end, 'RunLength' : runlength, 'Grade' : round(grade,2)})
                            runlength = 0
                            grade = 0
                            gradeton = 0
                            inorout = "out"

                    ## Closing run conditions ##
                    ## Condition where the hole ends 'in' ore. ##
                    if ((datatable[j][3]*length)+gradeton)/(runlength + length)>=cutoffgrade and inorout == "in" and (datatable[jplusone][0] != i):
                        results.append({'Holeid' : i, 'From' : beginning, 'To' : end, 'RunLength' : runlength, 'Grade' : round(grade,2)})
                        runlength = 0
                        grade = 0
                        gradeton = 0
                        inorout = "out"
                    ## Condition where we get to the end of the first run and commit the results ##
                    if ((datatable[j][3]*length)+gradeton)/(runlength + length)<cutoffgrade and inorout == "in":
                        ## Once at the end of the run, it goes back to check if adding the row prior to the run (as long as it's greater than mingradecutoff) keeps the entire run above grade) ##
                        if datatable[iteratornum][0] == i and iteratornum >= 0 and datatable[iteratornum][3] >= mingradecutoff and ((datatable[iteratornum][3]*gobacklength)+gradeton)/(runlength + gobacklength)>=cutoffgrade:
                            grade = ((datatable[iteratornum][3]*gobacklength)+gradeton)/(runlength + gobacklength)
                            beginning = datatable[iteratornum][1]
                            runlength = runlength + gobacklength
                        results.append({'Holeid' : i, 'From' : beginning, 'To' : end, 'RunLength' : runlength, 'Grade' : round(grade,2)})
                        runlength = 0
                        grade = 0
                        gradeton = 0
                        inorout = "out"
                        cherrypy.session['processeddata'] = results

        raise cherrypy.HTTPRedirect("/displayprocesseddata")

    ## Displays table of data ##
    @cherrypy.expose
    def displayprocesseddata(self):
        tmpl = env.get_template('exportdata.html')
        return tmpl.render(results = cherrypy.session['processeddata'])

application = cherrypy.Application(calculate(), '/', conf)
