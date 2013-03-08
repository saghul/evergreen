
Examples
========

A cooperative i/o library wouldn't be such without a "crawler" example:

::

    urls = ["http://google.com",
            "http://yahoo.com",
            "http://bing.com"]

    import flubber
    from flubber import futures, patcher
    urllib2 = patcher.import_patched('urllib2')

    loop = flubber.EventLoop()


    def fetch(url):
        return urllib2.urlopen(url).read()

    def work():
        executor = futures.TaskPoolExecutor(100)
        for body in executor.map(fetch, urls):
            print("got body {}".format(len(body)))

    flubber.spawn(work)
    loop.run()

