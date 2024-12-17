.PHONY: eval clean
.SECONDARY:

# latest wikipedia dump:
# LANG_WIKI_DUMP_URL = https://dumps.wikimedia.org/LANGwiki/latest/LANGwiki-latest-pages-articles.xml.bz2
LATEST_DUMP = 20241201
PL_WIKI_DUMP_URL = https://dumps.wikimedia.org/plwiki/${LATEST_DUMP}/plwiki-${LATEST_DUMP}-pages-articles.xml.bz2
UK_WIKI_DUMP_URL = https://dumps.wikimedia.org/ukwiki/${LATEST_DUMP}/ukwiki-${LATEST_DUMP}-pages-articles.xml.bz2
SK_WIKI_DUMP_URL = https://dumps.wikimedia.org/skwiki/${LATEST_DUMP}/skwiki-${LATEST_DUMP}-pages-articles.xml.bz2
RU_WIKI_DUMP_URL = https://dumps.wikimedia.org/ruwiki/${LATEST_DUMP}/ruwiki-${LATEST_DUMP}-pages-articles.xml.bz2
CS_WIKI_DUMP_URL = https://dumps.wikimedia.org/cswiki/${LATEST_DUMP}/cswiki-${LATEST_DUMP}-pages-articles.xml.bz2

eval: work/uk.frqwl work/sk.frqwl work/pl.frqwl work/cs.frqwl work/ru.frqwl work/uk.ipa.wls work/sk.ipa.wls work/pl.ipa.wls work/cs.ipa.wls work/ru.ipa.wls
	nice python optimize_params.py

repro: work/uk.frqwl work/sk.frqwl work/pl.frqwl work/cs.frqwl work/ru.frqwl work/uk.ipa.wls work/sk.ipa.wls work/pl.ipa.wls work/cs.ipa.wls work/ru.ipa.wls
	python evaluate_data_mix.py

work/%.ipa.wls: work/%.ipa.wlh
	tr -d '-' < $< > $@

wlh2ipawlh/target/release/wlh2ipawlh:
	cd wlh2ipawlh; RUSTFLAGS="-C target-cpu=native -C opt-level=3 -C codegen-units=1" cargo build --release
	mkdir -p work/ipacache

work/%.ipa.wlh: work/%.wlh wlh2ipawlh/target/release/wlh2ipawlh
	nice ./wlh2ipawlh/target/release/wlh2ipawlh $< $@

work/%.frqwl: work/%wikidir/.extraction_complete
	python wiki2frqwl.py work/$*wikidir $@

work/sk.wls: work/sk.frqwl
	python frqwl2wls.py --len=10000 work/sk.wls work/sk.frqwl

work/%.wls: work/%.frqwl
	python frqwl2wls.py $@ $<

work/%wikidir/.extraction_complete: work/%wiki-${LATEST_DUMP}-pages-articles.xml
	wikiextractor -o work/$*wikidir $<
	touch $@

%.xml: %.xml.bz2
	bzip2 -d $<

work/plwiki-${LATEST_DUMP}-pages-articles.xml.bz2:
	mkdir -p work
	wget ${PL_WIKI_DUMP_URL} -O $@

work/skwiki-${LATEST_DUMP}-pages-articles.xml.bz2:
	mkdir -p work
	wget ${SK_WIKI_DUMP_URL} -O $@

work/ukwiki-${LATEST_DUMP}-pages-articles.xml.bz2:
	mkdir -p work
	wget ${UK_WIKI_DUMP_URL} -O $@

work/ruwiki-${LATEST_DUMP}-pages-articles.xml.bz2:
	mkdir -p work
	wget ${RU_WIKI_DUMP_URL} -O $@

work/cswiki-${LATEST_DUMP}-pages-articles.xml.bz2:
	mkdir -p work
	wget ${CS_WIKI_DUMP_URL} -O $@

work/%wiki-${LATEST_DUMP}-pages-articles.xml.bz2:
	mkdir -p work
	wget https://dumps.wikimedia.org/$*wiki/${LATEST_DUMP}/$*wiki-${LATEST_DUMP}-pages-articles.xml.bz2 -O $@

# sh patterns are named differently (sh-latn) and Serbocroat wikipedia uses Latin script.
work/sh.wlh: work/sh.wls
	@if [ ! -f work/hyph-sh-latn.tex ]; then \
		wget https://raw.githubusercontent.com/hyphenation/tex-hyphen/master/hyph-utf8/tex/generic/hyph-utf8/patterns/tex/hyph-sh-latn.tex -O work/hyph-sh-latn.tex; \
	fi
	python hyph.py work/hyph-sh-latn.tex $< > $@.tmp && mv $@.tmp $@

work/csskhyphen.pat:
	@if [ ! -f work/csskhyphen.pat ]; then \
		wget https://raw.githubusercontent.com/tensojka/cshyphen/master/csskhyphen.pat -O work/csskhyphen.pat; \
	fi

work/sk.wlh: work/sk.wls work/csskhyphen.pat
	python hyph.py work/csskhyphen.pat $< > $@.tmp && mv $@.tmp $@

work/cs.wlh: work/cs.wls work/csskhyphen.pat
	python hyph.py work/csskhyphen.pat $< > $@.tmp && mv $@.tmp $@

work/%.wlh: work/%.wls
	@if [ ! -f work/hyph-$*.tex ]; then \
		wget https://raw.githubusercontent.com/hyphenation/tex-hyphen/master/hyph-utf8/tex/generic/hyph-utf8/patterns/tex/hyph-$*.tex -O work/hyph-$*.tex; \
	fi
	python hyph.py work/hyph-$*.tex $< > $@.tmp && mv $@.tmp $@

groundtruth/uk-full-wiktionary.wlh: work/ukwiktionary-20240920-pages-articles.xml parse_ground_truth.py
	python parse_ground_truth.py $< > $@

work/ukwiktionary-20240920-pages-articles.xml:
	wget -O work/ukwiktionary-20240920-pages-articles.xml.bz2 https://dumps.wikimedia.org/ukwiktionary/20240920/ukwiktionary-20240920-pages-articles.xml.bz2
	bzip2 -d work/ukwiktionary-20240920-pages-articles.xml.bz2

clean:
	rm -rf work/*