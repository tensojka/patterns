.PHONY: all clean

all: work/cs.frqwl

work/%.frqwl: work/%
	python wiki2frqwl.py $< $@

work/%.wls: work/%.frqwl
	python frqwl2wls.py $@ $<

work/%: work/%wiki-latest-pages-articles.xml
	wikiextractor -o $@ $<

%.xml: %.xml.bz2
	bzip2 -d $<

work/%wiki-latest-pages-articles.xml.bz2:
	wget https://dumps.wikimedia.org/$*wiki/latest/$*wiki-latest-pages-articles.xml.bz2 -O $@

clean:
	rm -rf work/*