/**
 * CareerOS Content Script — Job Data Extractor
 *
 * Runs on supported job board pages to auto-extract job details.
 * Does NOT modify the page — only reads DOM and responds to messages.
 */

// ── Extractors by domain ─────────────────────────────────────

const extractors = {
  /**
   * LinkedIn job page extractor
   */
  linkedin() {
    const title =
      document.querySelector('.job-details-jobs-unified-top-card__job-title h1')?.textContent?.trim() ||
      document.querySelector('.t-24.t-bold')?.textContent?.trim() ||
      document.querySelector('.jobs-unified-top-card__job-title')?.textContent?.trim() ||
      '';

    const company =
      document.querySelector('.job-details-jobs-unified-top-card__company-name a')?.textContent?.trim() ||
      document.querySelector('.jobs-unified-top-card__company-name a')?.textContent?.trim() ||
      '';

    const location =
      document.querySelector('.job-details-jobs-unified-top-card__bullet')?.textContent?.trim() ||
      document.querySelector('.jobs-unified-top-card__bullet')?.textContent?.trim() ||
      '';

    // Extract skills from job description
    const descEl = document.querySelector('.jobs-description-content__text') ||
                   document.querySelector('.jobs-box__html-content');
    const skills = descEl ? extractSkillsFromText(descEl.textContent) : '';

    return { title, company, location, skills };
  },

  /**
   * Indeed job page extractor
   */
  indeed() {
    const title =
      document.querySelector('.jobsearch-JobInfoHeader-title')?.textContent?.trim() ||
      document.querySelector('[data-testid="jobsearch-JobInfoHeader-title"]')?.textContent?.trim() ||
      document.querySelector('h1.icl-u-xs-mb--xs')?.textContent?.trim() ||
      '';

    const company =
      document.querySelector('[data-testid="inlineHeader-companyName"]')?.textContent?.trim() ||
      document.querySelector('.icl-u-lg-mr--sm')?.textContent?.trim() ||
      '';

    const location =
      document.querySelector('[data-testid="inlineHeader-companyLocation"]')?.textContent?.trim() ||
      document.querySelector('.icl-u-xs-mt--xs .icl-u-textColor--vcentered')?.textContent?.trim() ||
      '';

    const descEl = document.querySelector('#jobDescriptionText');
    const skills = descEl ? extractSkillsFromText(descEl.textContent) : '';

    return { title, company, location, skills };
  },

  /**
   * Naukri job page extractor
   */
  naukri() {
    const title =
      document.querySelector('.jd-header-title')?.textContent?.trim() ||
      document.querySelector('h1.styles_jd-header-title__rZwM1')?.textContent?.trim() ||
      '';

    const company =
      document.querySelector('.jd-header-comp-name a')?.textContent?.trim() ||
      document.querySelector('.styles_jd-header-comp-name__MvDmI a')?.textContent?.trim() ||
      '';

    const location =
      document.querySelector('.location')?.textContent?.trim() ||
      document.querySelector('.styles_jhc__loc___Du2H')?.textContent?.trim() ||
      '';

    // Naukri has skill tags
    const skillEls = document.querySelectorAll('.chip_chip__sBwmW, .key-skill .chip, .styles_chip__7YCfG');
    const skills = Array.from(skillEls)
      .map((el) => el.textContent?.trim())
      .filter(Boolean)
      .join(', ');

    return { title, company, location, skills };
  },

  /**
   * IIMJobs job page extractor
   */
  iimjobs() {
    const title =
      document.querySelector('.jd-title h1')?.textContent?.trim() ||
      document.querySelector('.job-header h1')?.textContent?.trim() ||
      '';

    const company =
      document.querySelector('.jd-company')?.textContent?.trim() ||
      document.querySelector('.company-name')?.textContent?.trim() ||
      '';

    const location =
      document.querySelector('.jd-location')?.textContent?.trim() ||
      '';

    const descEl = document.querySelector('.job-description') || document.querySelector('.jd-desc');
    const skills = descEl ? extractSkillsFromText(descEl.textContent) : '';

    return { title, company, location, skills };
  },
};

// ── Skill Extraction Helper ──────────────────────────────────

const COMMON_SKILLS = [
  'python', 'javascript', 'typescript', 'java', 'sql', 'react', 'node.js',
  'aws', 'gcp', 'azure', 'docker', 'kubernetes', 'git', 'agile', 'scrum',
  'product management', 'data analysis', 'machine learning', 'deep learning',
  'excel', 'power bi', 'tableau', 'google analytics', 'a/b testing',
  'stakeholder management', 'project management', 'business analysis',
  'user research', 'wireframing', 'figma', 'jira', 'confluence',
  'financial modeling', 'strategy', 'consulting', 'marketing',
  'supply chain', 'operations', 'sales', 'crm', 'salesforce',
  'html', 'css', 'rest api', 'graphql', 'mongodb', 'postgresql',
  'redis', 'kafka', 'spark', 'hadoop', 'tensorflow', 'pytorch',
];

function extractSkillsFromText(text) {
  if (!text) return '';
  const textLower = text.toLowerCase();
  const found = COMMON_SKILLS.filter((skill) => textLower.includes(skill));
  return found.slice(0, 10).join(', ');
}

// ── Detect current site ──────────────────────────────────────

function getExtractor() {
  const host = window.location.hostname;
  if (host.includes('linkedin.com')) return extractors.linkedin;
  if (host.includes('indeed.com') || host.includes('indeed.co.in')) return extractors.indeed;
  if (host.includes('naukri.com')) return extractors.naukri;
  if (host.includes('iimjobs.com')) return extractors.iimjobs;
  return null;
}

// ── Message Handler ──────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.action === 'extractJobData') {
    const extractor = getExtractor();
    if (extractor) {
      try {
        const data = extractor();
        sendResponse(data);
      } catch (err) {
        console.error('[CareerOS] Extraction error:', err);
        sendResponse({ title: '', company: '', location: '', skills: '' });
      }
    } else {
      sendResponse({ title: '', company: '', location: '', skills: '' });
    }
    return true; // Keep message channel open for async response
  }
});
