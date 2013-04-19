
from evergreen import futures, patcher
urllib2 = patcher.import_patched('urllib2')

urls = ["http://google.com",
        "http://yahoo.com",
        "http://bing.com"]


def fetch(url):
    return urllib2.urlopen(url).read()

executor = futures.TaskPoolExecutor(100)
for body in executor.map(fetch, urls):
    print("got body {}".format(len(body)))

