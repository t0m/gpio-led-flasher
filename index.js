"use strict";

const puppeteer = require('puppeteer');
(async () => {
  const browser = await puppeteer.launch({
        executablePath: '/usr/bin/chromium-browser',
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',

        ]
  });
  const page = await browser.newPage();
  await page.goto('https://www.arcgis.com/apps/opsdashboard/index.html#/85320e2ea5424dfaaa75ae62e5c06e61');
  await page.waitFor(15000);

  const selector = ".indicator-widget text"
  await page.waitForSelector(selector);
  const textContent = await page.evaluate(() => {
     const selector = ".indicator-widget text"
     return Array.from(document.querySelectorAll(selector), (e) => e.innerHTML)
  });

  let totalConfirmed = null;
  let totalDeaths = null;

  for (var x=0; x<textContent.length; x++) {
    if (totalConfirmed === null && textContent[x] == 'Total Confirmed') {
      totalConfirmed = parseInt(textContent[x+1].replace(/,/g, ''));
      ++x;
    } else if (textContent[x] == 'Total Deaths') {
      totalDeaths = parseInt(textContent[x+1].replace(/,/g, ''));
      ++x;
    }
  }

  await browser.close();

  console.log('{"totalConfirmed": ' + totalConfirmed + ', "totalDeaths": ' + totalDeaths + "}");
})();

