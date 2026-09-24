// Facts shown on the site. Every number here comes from the repo's eval reports
// (docs/POLICY_EVAL.md, docs/FINDINGS.md, docs/PROGRESS.md, reports/). Update them together.

export const GITHUB_URL = "https://github.com/MoZainUlAbideen/rehnuma";

export interface PolicyDoc {
  short: string;
  title: string;
  year: string;
  status: "in_force" | "repealed";
  clauses: number;
  url: string;
  what: string;
}

const NEPRA = "https://nepra.org.pk/Legislation";

export const DOCUMENTS: PolicyDoc[] = [
  {
    short: "Prosumer Regulations 2026",
    title: "NEPRA (Prosumer) Regulations, 2026 - S.R.O. 251(I)/2026",
    year: "2026",
    status: "in_force",
    clauses: 90,
    url: `${NEPRA}/3-Reg/3.35%20NEPRA%20%20Prosumer%20Regulations%202026/NEPRA%20Prosumer%20Regulations%20(SRO%20251(I)2026)%2009-02-26.PDF`,
    what: "Today's rules for rooftop solar: net billing, buyback rates, and which old agreements keep their terms (reg. 21(2)).",
  },
  {
    short: "Consumer Service Manual 2025",
    title: "Consumer Service Manual (CSM), revised 2025",
    year: "2025",
    status: "in_force",
    clauses: 400,
    url: `${NEPRA}/7-Manuals/2025/CONSUMER%20SERVICE%20MANUAL%20(CSM)%20REVISED%202025.pdf`,
    what: "How DISCOs must bill, read meters, handle complaints, detection bills and disconnections.",
  },
  {
    short: "Net Metering Regulations 2015",
    title:
      "NEPRA (Alternative & Renewable Energy) Distributed Generation and Net Metering Regulations, 2015 - S.R.O. 892(I)/2015",
    year: "2015",
    status: "repealed",
    clauses: 71,
    url: `${NEPRA}/3-Reg/3.13%20NEPRA%20(Alternative%20&%20Renewable%20Energy)%20Distributed%20Generation%20and%20Net%20Metering%20Regulations,%202015/NOTIFICATION%20SRO%20892%20-2015.pdf`,
    what: "The old net-metering rules. Repealed, but still govern existing agreements until they end.",
  },
  {
    short: "Amendment 2017",
    title: "Amendment to the Net Metering Regulations 2015 - S.R.O. 1025(I)/2017",
    year: "2017",
    status: "repealed",
    clauses: 1,
    url: `${NEPRA}/3-Reg/3.13%20NEPRA%20(Alternative%20&%20Renewable%20Energy)%20Distributed%20Generation%20and%20Net%20Metering%20Regulations,%202015/SRO%201025(I)2017%2010-10-2017.pdf`,
    what: "Amends the 2015 regulations.",
  },
  {
    short: "Amendment 2018",
    title: "Amendment to the Net Metering Regulations 2015 - S.R.O. 1135(I)/2018",
    year: "2018",
    status: "repealed",
    clauses: 4,
    url: `${NEPRA}/3-Reg/3.13%20NEPRA%20(Alternative%20&%20Renewable%20Energy)%20Distributed%20Generation%20and%20Net%20Metering%20Regulations,%202015/S.R.O%201135(I)-2018%2013-09-2018.pdf`,
    what: "Amends the 2015 regulations.",
  },
];

export const TOTAL_CLAUSES = DOCUMENTS.reduce((n, d) => n + d.clauses, 0);
