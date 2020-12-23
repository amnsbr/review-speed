# Journal Review Speed Scraper
Knowing the review speed of journals is often very important when researchers are choosing a journal to publish their work. Publishers such as Elsevier and Springer do report the review speeds, but often as an average number, with and unknown distribution and/or time window. This package scrapes the webpages of articles and using publisher-specific patterns/functions parses their submission, acceptance, and publication dates. Given a journal's abbreviated name, it searches PubMed for its latest (default: 50) articles, and saves their dates and review speeds in a pandas DataFrame. This can later be used to look at the distribution of review speed, or to get e.g., the 80th percentile of review speed.

These are the currently supported publishers:
- Elsevier
- Springer
- Karger
- Hindawi
- Taylor and Francis
- Scielo
However, this may not work for some journals of these publishers, as they may not have reported their submission, acceptance and publication dates.

Currently the input and output is not optimal and needs further work. Also, as the parsing is based on specific regex patters or specific html elements, I expect this to be unstable, and continous testing and updating would be needed for maintaining it. Contributions are welcomed for maintanance and supporting more publishers.