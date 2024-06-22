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

%.wlh: %.wls
	echo "beware, expects Czech/Slovak by default"
	recode UTF8..ISO-8859-2 $<
	printf "%s\n%s\n%s\n%s" "1 1" \
	"1 1" \
	"1 1 1" \
	"y" \
	| ./patgen $< ~/cshyphen/csskhyphen.pat /dev/null ~/cshyphen/czech.tra
	mv pattmp.1 $@
	recode ISO-8859-2..UTF8 $<
	recode ISO-8859-2..UTF8 $@
	sed -i -e 's/\./-/g' $@

clean:
	rm -rf work/*