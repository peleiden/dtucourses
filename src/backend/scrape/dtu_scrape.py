from os import chdir, getcwd
from os.path import dirname, realpath
chdir(realpath(dirname(__file__)))

from bs4 import BeautifulSoup
import multiprocessing as mp

from grade_scraper import scrape_all_grades
from eval_scraper import scrape_all_evals
chdir(getcwd() + "/../../..")

import json
import time
import sys
from selenium import webdriver

URL = "http://kurser.dtu.dk/search?CourseCode=&SearchKeyword=&Department=1&Department=10&Department=11&Department=12&Department=13&Department=22&Department=23&Department=24&Department=25&Department=26&Department=27&Department=28&Department=29&Department=30&Department=31&Department=33&Department=34&Department=36&Department=38&Department=41&Department=42&Department=46&Department=47&Department=59&Department=IHK&Department=83&CourseType=&TeachingLanguage="

sys.setrecursionlimit(25000)

def get_full_course_list_html() -> str:
	"""
	Get list of all courses as html page. HTML when going to URL
	Requires geckodriver to work (install on arch with sudo pacman -S geckodriver)
	"""
	print("Starting Firefox in headless mode")
	options = webdriver.FirefoxOptions()
	options.add_argument("--headless")
	browser = webdriver.Firefox(options = options)
	print("Getting list of all courses")
	browser.get(URL)
	time.sleep(10)
	browser.execute_script("javascript:setLanguage('da-DK')")
	time.sleep(10)
	return browser.page_source

def get_course_information():
	courses = list()

	soup =  BeautifulSoup(get_full_course_list_html(), "html.parser")

	result = soup.find(class_ = "panel panel-default")
	course_objects = result.table.tbody.find_all("tr")

	for course in course_objects:
		# Skip headers
		if len(course.contents) < 4:
			continue

		info = dict()

		# Using leftmost course information
		course.contents[3].small
		info_string = course.contents[3].small.contents[0]
		info_list = info_string.split("|")

		# Course language and ECTS
		info["language"] = info_list[0].strip()
		ects_str = info_list[1].split()[0]
		try:
			info["ECTS"] = int(ects_str)
		except ValueError:
			info["ECTS"] = float(ects_str)

		# Course time
		time_data = course.contents[3].small.contents[3:]
		info["time"] = " ".join([str(td.string).strip() if td.string is not None else "" for td in time_data]).strip()

		# Course level
		info["level"] = course.contents[5].string.strip()

		# Course name
		course_name = course.a.string[course.a.string.index("-")+1:]
		info["name"] = course_name.strip()

		# Course number
		course_link = course.a["href"]
		course_n = course_link.split("/")[-1]
		info["course_no"] = course_n

		courses.append(
			{"info": info}
		)
	return courses

def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]

def scrape_all(N_processes = 12):
	'''
	Scrapes all course information, grades, evaluations for each course.
	'''
	nowtime = time.strftime('%Y-%m-%dT%H%M%S', time.localtime())
	cleantime = nowtime.split('T')[0]
	course_dict = dict()

	with open("src/backend/data/time.txt", "w") as f:
		f.write(cleantime)
	course_dict["time"] = cleantime

	print("Reading course information ... ")
	course_list = get_course_information()

	print("Beginning scrape of %s courses ... " % len(course_list))

	#multiprocessing of course downloads
	with mp.Pool(processes = N_processes) as p:
		mushed_course_list = p.map(scrape_loop, chunks(course_list, len(course_list) // N_processes))
	course_list = [item for sublist in mushed_course_list for item in sublist]

#	course_list = scrape_loop(course_list)
	for course in course_list:
		course_dict[course["info"]["course_no"]] = course

	print("N found courses:", len(course_list))

	with open('src/backend/data/complete_raw_data.json', 'w+') as fp:
		json.dump(course_dict, fp, indent=4)

def scrape_loop(course_list):
	N = len(course_list)

	for i, course in enumerate(course_list):
		error = 0
		number = course["info"]["course_no"]
		try:
			grade_info = scrape_all_grades(number)
			course["grades"] = grade_info
		except Exception as e:
			course["grades"] = {}
			error = 1
			print("\tGrade error", number, e)

		try:
			eval_info = scrape_all_evals(number)
			course["evals"] = eval_info

		except Exception as e:
			error = 1
			print("\tEval error", number, e)

		if not error:
			print("Completely scraped %s (%s/%s)" %(number, i+1, N))

	return course_list

if __name__ == "__main__":
	scrape_all(N_processes = 4 * mp.cpu_count())
