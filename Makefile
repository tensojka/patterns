.PHONY: all clean
.SECONDARY:

all: work/cs.frqwl

work/%.ipa.wls: work/%.ipa.wlh
	tr -d '-' < $< > $@

work/%.ipa.wlh: work/%.wlh
	cd wlh2ipawlh; RUSTFLAGS="-C target-cpu=native -C opt-level=3 -C codegen-units=1" cargo build --release
	nice ./wlh2ipawlh/target/release/wlh2ipawlh $< $@

work/%.frqwl: work/%wikidir
	python wiki2frqwl.py $< $@

work/%.wls: work/%.frqwl
	python frqwl2wls.py $@ $<

work/%wikidir: work/%wiki-latest-pages-articles.xml
	wikiextractor -o $@ $<

%.xml: %.xml.bz2
	bzip2 -d $<

work/%wiki-latest-pages-articles.xml.bz2:
	wget https://dumps.wikimedia.org/$*wiki/latest/$*wiki-latest-pages-articles.xml.bz2 -O $@

# sh patterns are named differently (sh-latn) and Serbocroat wikipedia uses Latin script.
work/sh.wlh: work/sh.wls
	@if [ ! -f work/hyph-sh-latn.tex ]; then \
		wget https://raw.githubusercontent.com/hyphenation/tex-hyphen/master/hyph-utf8/tex/generic/hyph-utf8/patterns/tex/hyph-sh-latn.tex -O work/hyph-sh-latn.tex; \
	fi
	python hyph.py work/hyph-sh-latn.tex $< > $@

work/csskhyphen.pat:
	@if [ ! -f work/csskhyphen.pat ]; then \
		wget https://raw.githubusercontent.com/tensojka/cshyphen/master/csskhyphen.pat -O work/csskhyphen.pat; \
	fi

work/sk.wlh: work/sk.wls work/csskhyphen.pat
	python hyph.py work/csskhyphen.pat $< > $@

work/cs.wlh: work/cs.wls work/csskhyphen.pat
	python hyph.py work/csskhyphen.pat $< > $@

work/%.wlh: work/%.wls
	@if [ ! -f work/hyph-$*.tex ]; then \
		wget https://raw.githubusercontent.com/hyphenation/tex-hyphen/master/hyph-utf8/tex/generic/hyph-utf8/patterns/tex/hyph-$*.tex -O work/hyph-$*.tex; \
	fi
	python hyph.py work/hyph-$*.tex $< > $@

groundtruth/uk-full-wiktionary.wlh: work/ukwiktionary-20240920-pages-articles.xml parse_ground_truth.py
	python parse_ground_truth.py $< > $@

work/ukwiktionary-20240920-pages-articles.xml:
	wget -O work/ukwiktionary-20240920-pages-articles.xml.bz2 https://dumps.wikimedia.org/ukwiktionary/20240920/ukwiktionary-20240920-pages-articles.xml.bz2
	bzip2 -d work/ukwiktionary-20240920-pages-articles.xml.bz2

eval: work/uk.wlh work/uk.ipa.wls work/ru.wlh work/ru.ipa.wls work/sk.wlh work/sk.ipa.wls work/pl.wlh work/pl.ipa.wls

clean:
	rm -rf work/*