---
title: "Search Assistant"
layout: page
permalink: "/ai-assistant"
description: "A lightweight on-site search assistant for the UMass Boston Computer Science Department website."
keywords:
  - "Search Assistant"
  - "Site Search"
  - "UMass Boston Computer Science"
  - "Courses"
  - "Programs"
  - "Resources"
---

<div class="ai-assistant-search">
  <label for="ai-assistant-query"><strong>Search the site</strong></label>
  <div class="ai-assistant-controls">
    <input
      id="ai-assistant-query"
      type="text"
      placeholder="Search courses, faculty, programs, groups, and resources"
      autocomplete="off"
    >
    <button id="ai-assistant-button" type="button">Search</button>
  </div>
  <div id="ai-assistant-status" class="ai-assistant-status">Search courses, faculty, programs, groups, and resources.</div>
  <div id="ai-assistant-answer" class="ai-assistant-answer" aria-live="polite" hidden></div>
  <div id="ai-assistant-debug" class="ai-assistant-debug" hidden></div>
  <div id="ai-assistant-results" class="ai-assistant-results" aria-live="polite"></div>
</div>

<style>
  .ai-assistant-search {
    margin: 1.5rem auto 0;
    max-width: 52rem;
  }

  .ai-assistant-controls {
    display: flex;
    gap: 0.75rem;
    margin: 0.75rem 0 1rem;
    flex-wrap: wrap;
    align-items: center;
  }

  .ai-assistant-controls input {
    flex: 1 1 24rem;
    min-width: 16rem;
    padding: 0.75rem;
    font: inherit;
  }

  .ai-assistant-controls button {
    padding: 0.75rem 1rem;
    font: inherit;
    cursor: pointer;
  }

  .ai-assistant-status {
    margin-bottom: 1rem;
  }

  .ai-assistant-results {
    display: grid;
    gap: 1rem;
  }

  .ai-assistant-answer {
    margin: 0 0 1rem;
    padding: 1rem;
    border: 1px solid #d7d7d7;
    background: #f8f8f8;
  }

  .ai-assistant-answer ul {
    margin: 0;
    padding-left: 1.25rem;
  }

  .ai-assistant-answer li + li {
    margin-top: 0.75rem;
  }

  .ai-assistant-debug {
    margin: 0 0 1rem;
    padding: 1rem;
    border: 1px dashed #c7c7c7;
    background: #fcfcfc;
    font-size: 0.95rem;
  }

  .ai-assistant-debug h2 {
    margin: 0 0 0.75rem;
    font-size: 1.05rem;
  }

  .ai-assistant-debug h3 {
    margin: 0 0 0.5rem;
    font-size: 1rem;
  }

  .ai-assistant-debug p {
    margin: 0 0 0.75rem;
  }

  .ai-assistant-debug ul {
    margin: 0 0 1rem;
    padding-left: 1.25rem;
  }

  .ai-assistant-debug code {
    font-size: 0.95em;
  }

  .ai-assistant-result {
    border: 1px solid #d7d7d7;
    padding: 1rem;
    background: #fff;
  }

  .ai-assistant-result-header {
    display: flex;
    gap: 0.75rem;
    justify-content: space-between;
    align-items: flex-start;
    flex-wrap: wrap;
    margin-bottom: 0.5rem;
  }

  .ai-assistant-result h3 {
    margin: 0;
    font-size: 1.05rem;
  }

  .ai-assistant-result p {
    margin: 0 0 0.75rem;
  }

  .ai-assistant-type {
    display: inline-block;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
    font-size: 0.85rem;
    line-height: 1.3;
    font-weight: 600;
    white-space: nowrap;
    border: 1px solid transparent;
  }

  .ai-assistant-type-course {
    background: #eef5ff;
    color: #184a90;
    border-color: #c8daf7;
  }

  .ai-assistant-type-person {
    background: #eef8f0;
    color: #25613a;
    border-color: #cde6d3;
  }

  .ai-assistant-type-program {
    background: #fff4ea;
    color: #8f4a12;
    border-color: #f0d6bc;
  }

  .ai-assistant-type-group {
    background: #f4efff;
    color: #5d3aa0;
    border-color: #ddd2f7;
  }

  .ai-assistant-type-department {
    background: #f1f1f1;
    color: #3f3f3f;
    border-color: #d8d8d8;
  }

  .ai-assistant-type-page {
    background: #f2f6f2;
    color: #34543b;
    border-color: #d7e4d9;
  }

  .ai-assistant-type-resource {
    background: #eef8fb;
    color: #1e596c;
    border-color: #cfe2ea;
  }

  .ai-assistant-type-facility {
    background: #fff7e8;
    color: #8a5a12;
    border-color: #ecd8b2;
  }

  .ai-assistant-meta {
    margin: 0 0 0.75rem;
    color: #555;
    font-size: 0.95rem;
  }

  .ai-assistant-explanation {
    margin-bottom: 0.75rem;
  }

  .ai-assistant-link {
    font-weight: 600;
  }

  .ai-assistant-related {
    margin: 0.75rem 0 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid #ececec;
  }

  .ai-assistant-related h4 {
    margin: 0 0 0.5rem;
    font-size: 0.98rem;
  }

  .ai-assistant-related ul {
    margin: 0;
    padding-left: 1.25rem;
  }

  .ai-assistant-related li + li {
    margin-top: 0.35rem;
  }
</style>

<script>
  (function() {
    const queryInput = document.getElementById('ai-assistant-query');
    const searchButton = document.getElementById('ai-assistant-button');
    const statusNode = document.getElementById('ai-assistant-status');
    const answerNode = document.getElementById('ai-assistant-answer');
    const debugNode = document.getElementById('ai-assistant-debug');
    const resultsNode = document.getElementById('ai-assistant-results');
    const dataUrl = '{{ "/ai/index.json" | relative_url }}';
    const configuredSiteRoot = {{ '/' | absolute_url | jsonify }};
    const maxContextEntities = 4;
    const debugQueries = [
      'chimera',
      'hpc',
      'high performance computing',
      'research computing',
      'unity',
      'computer vision',
      'algorithms',
      'bioinformatics',
      'machine learning professor',
      'graduate program',
      'graduate program data science',
      'data science group',
      'faculty',
      'advising',
      'internship',
      'student resources',
      'gpu',
      'cluster'
    ];
    const stopWords = new Set([
      'a', 'an', 'and', 'are', 'for', 'from', 'how', 'i', 'in', 'is', 'me', 'of', 'on', 'or',
      'related', 'show', 'tell', 'that', 'the', 'to', 'what', 'who', 'works'
    ]);
    const navigationTerms = new Set([
      'about', 'academics', 'people', 'research', 'resources', 'updates', 'news',
      'events', 'faculty', 'staff', 'funding', 'groups', 'computing', 'programs',
      'advising', 'internship', 'internships'
    ]);
    const tokenSynonyms = {
      ai: ['artificial', 'intelligence'],
      professor: ['faculty'],
      faculty: ['professor'],
      lab: ['laboratory', 'group'],
      laboratory: ['lab', 'group'],
      group: ['lab', 'laboratory'],
      hpc: ['high', 'performance', 'computing', 'cluster'],
      gpu: ['gpus'],
      cluster: ['hpc'],
      course: ['courses', 'class'],
      courses: ['course', 'classes'],
      class: ['course', 'courses'],
      classes: ['course', 'courses'],
      program: ['programs', 'degree'],
      programs: ['program', 'degree'],
      degree: ['program', 'programs'],
      faculty: ['professor', 'instructor'],
      professor: ['faculty', 'instructor'],
      instructor: ['faculty', 'professor'],
      research: ['researching', 'researcher'],
      computing: ['computer', 'computation'],
      advising: ['advisor', 'advisors'],
      advisor: ['advising', 'advisors'],
      internship: ['internships', 'jobs', 'careers'],
      internships: ['internship', 'jobs', 'careers'],
      job: ['jobs', 'career', 'internship'],
      jobs: ['job', 'careers', 'internships'],
      career: ['careers', 'jobs', 'internship'],
      careers: ['career', 'jobs', 'internships']
    };
    let searchIndex = null;
    let relationMaps = null;

    function escapeHtml(value) {
      return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function normalizeText(value) {
      if (Array.isArray(value)) {
        return value.join(' ');
      }

      if (value === null || value === undefined) {
        return '';
      }

      return String(value)
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
    }

    function tokenizeText(value) {
      return normalizeText(value).split(/\s+/).filter(Boolean);
    }

    function normalizeQuery(value) {
      const normalized = normalizeText(value);
      const baseTokens = tokenizeText(value).filter((token) => !stopWords.has(token));
      const expandedTokens = [];

      baseTokens.forEach((token) => {
        expandedTokens.push(token);

        if (token.length > 3 && token.endsWith('s')) {
          expandedTokens.push(token.slice(0, -1));
        } else if (token.length > 3) {
          expandedTokens.push(`${token}s`);
        }

        if (tokenSynonyms[token]) {
          expandedTokens.push.apply(expandedTokens, tokenSynonyms[token]);
        }
      });

      return {
        raw: normalized,
        compact: normalized.replace(/\s+/g, ''),
        tokens: Array.from(new Set(expandedTokens.filter(Boolean)))
      };
    }

    function toArray(value) {
      if (Array.isArray(value)) {
        return value;
      }

      if (!value) {
        return [];
      }

      return [value];
    }

    function buildIndex(data) {
      return (data.entities || []).map((entity) => {
        const normalizedUrl = sanitizeEntityUrl(entity.url || '');
        const slugSource = normalizedUrl.split('/').filter(Boolean).pop() || entity.id || '';
        const title = entity.title || '';

        return {
          id: entity.id || '',
          type: entity.type || 'entity',
          title,
          courseCode: entity.course_code || '',
          courseName: entity.course_name || '',
          personName: entity.person_name || '',
          jobTitle: entity.job_title || '',
          url: normalizedUrl,
          summary: entity.summary || '',
          keywords: toArray(entity.keywords),
          aliases: toArray(entity.aliases),
          relatedPeople: toArray(entity.related_people),
          relatedPeopleNames: toArray(entity.related_people_names),
          relatedCourses: toArray(entity.related_courses),
          relatedGroups: toArray(entity.related_groups),
          relatedPrograms: toArray(entity.related_programs),
          relatedTopics: toArray(entity.related_topics),
          researchAreas: toArray(entity.research_areas),
          teachesCourses: toArray(entity.teaches_courses),
          currentTeachingTerms: toArray(entity.current_teaching_terms),
          teachingAcademicYears: toArray(entity.teaching_academic_years),
          externalResearchTopics: toArray(entity.external_research_topics),
          labOrGroup: toArray(entity.lab_or_group),
          profileLinks: toArray(entity.profile_links),
          sourceUrls: toArray(entity.source_urls),
          recentNewsTitles: toArray(entity.recent_news_titles),
          instructors: toArray(entity.instructors),
          offeringsTerms: toArray(entity.offerings_terms),
          offeringsAcademicYears: toArray(entity.offerings_academic_years),
          instructorTopics: toArray(entity.instructor_topics),
          navLabel: entity.nav_label || '',
          sectionName: entity.section_name || '',
          parentSection: entity.parent_section || '',
          isLandingPage: Boolean(entity.is_landing_page),
          menuKeywords: toArray(entity.menu_keywords),
          slug: normalizeText(slugSource).replace(/-/g, ' ')
        };
      });
    }

    function buildRelationMaps(index) {
      const groupTopicsByPersonId = new Map();

      index.forEach((item) => {
        if (item.type !== 'group') {
          return;
        }

        item.relatedPeople.forEach((personSlug) => {
          const personId = `person:${personSlug}`;
          const existing = groupTopicsByPersonId.get(personId) || [];
          groupTopicsByPersonId.set(
            personId,
            existing.concat(item.relatedTopics, item.keywords, item.aliases, item.title)
          );
        });
      });

      return {
        groupTopicsByPersonId
      };
    }

    function getEntityLabel(type) {
      const labels = {
        department: 'Department',
        course: 'Course',
        person: 'Person',
        program: 'Program',
        group: 'Research Group',
        page: 'Page',
        resource: 'Resource',
        facility: 'Facility'
      };

      return labels[type] || 'Result';
    }

    function getEntityTypeClass(type) {
      const classes = {
        department: 'ai-assistant-type-department',
        course: 'ai-assistant-type-course',
        person: 'ai-assistant-type-person',
        program: 'ai-assistant-type-program',
        group: 'ai-assistant-type-group',
        page: 'ai-assistant-type-page',
        resource: 'ai-assistant-type-resource',
        facility: 'ai-assistant-type-facility'
      };

      return classes[type] || 'ai-assistant-type-department';
    }

    function buildExplanation(item) {
      const label = getEntityLabel(item.type);
      const summary = item.summary || 'No summary available.';
      const cleanedSummary = summary.replace(/\s+/g, ' ').trim();

      return `${label}: ${cleanedSummary}`;
    }

    function isLocalHost(hostname) {
      return /^(localhost|127(?:\.\d{1,3}){3})$/i.test(hostname || '');
    }

    function isProductionPage() {
      return window.location && !isLocalHost(window.location.hostname);
    }

    function isDebugMode() {
      try {
        const params = new URLSearchParams(window.location.search);
        return !isProductionPage() || params.get('debug') === '1';
      } catch (error) {
        return !isProductionPage();
      }
    }

    function sanitizeEntityUrl(rawUrl) {
      if (!rawUrl) {
        return '';
      }

      try {
        const configuredRoot = new URL(configuredSiteRoot);
        const resolved = new URL(rawUrl, configuredRoot);

        if (isProductionPage() && isLocalHost(resolved.hostname)) {
          return new URL(
            `${resolved.pathname}${resolved.search}${resolved.hash}`,
            configuredRoot
          ).toString();
        }

        if (!/^https?:$/i.test(resolved.protocol)) {
          return '';
        }

        return resolved.toString();
      } catch (error) {
        return '';
      }
    }

    function buildCompactEntity(item) {
      return {
        title: item.title,
        type: item.type,
        summary: item.summary || '',
        url: sanitizeEntityUrl(item.url)
      };
    }

    function isNavigationQuery(query) {
      const normalizedQuery = normalizeQuery(query);
      const raw = normalizedQuery.raw;
      const tokens = normalizedQuery.tokens.filter(Boolean);

      if (!raw) {
        return false;
      }

      if (raw === 'news and events' || raw === 'student resources') {
        return true;
      }

      return tokens.length <= 2 && tokens.some((token) => navigationTerms.has(token));
    }

    function buildPromptPayload(query, results) {
      const entities = results.slice(0, maxContextEntities).map(buildCompactEntity);
      const systemMessage = [
        'You are a CS department assistant for the UMass Boston Computer Science Department.',
        'ONLY use the provided entities.',
        'DO NOT invent courses, people, programs, groups, facilities, or resources.',
        'If unsure or if there is no exact match, say "No exact match found."',
        'Return concise structured results.',
        'Use only each entity title, type, summary, and url.',
        'Output plain text bullet lines in this exact format:',
        '- Title (Type): short explanation. Link: URL'
      ].join(' ');
      const userPayload = {
        query: query.trim(),
        instructions: {
          use_only_retrieved_entities: true,
          do_not_invent_entities: true,
          no_full_site_content: true,
          concise_grounded_output: true,
          output_format: '- Title (Type): short explanation. Link: URL'
        },
        retrieved_entities: entities
      };

      return {
        query: query.trim(),
        entities,
        messages: [
          { role: 'system', content: systemMessage },
          { role: 'user', content: JSON.stringify(userPayload) }
        ]
      };
    }

    function scoreField(text, queryText, queryTokens, weights) {
      if (!text) {
        return 0;
      }

      let score = 0;
      const fieldTokens = tokenizeText(text);
      const singleTokenQuery = !queryText.includes(' ');
      const partialMatch = singleTokenQuery
        ? fieldTokens.includes(queryText)
        : text.includes(queryText);

      if (text === queryText) {
        score += weights.exact || 0;
      } else if (partialMatch) {
        score += weights.partial || 0;
      }

      for (const token of queryTokens) {
        if (fieldTokens.includes(token)) {
          score += weights.token || 0;
        }
      }

      return score;
    }

    function scoreArray(values, queryText, queryTokens, weights) {
      return values.reduce((total, value) => total + scoreField(normalizeText(value), queryText, queryTokens, weights), 0);
    }

    function countTokenHits(queryTokens, fields) {
      return queryTokens.reduce((count, token) => {
        return count + (fields.some((field) => {
          const fieldTokens = tokenizeText(field);
          return fieldTokens.includes(token);
        }) ? 1 : 0);
      }, 0);
    }

    function inferIntent(queryText) {
      return {
        person: /(professor|faculty|chair|lecturer|instructor|researcher|who works)/.test(queryText),
        course: /(course|courses|class|classes|cs\s?\d{3}|it\s?\d{3})/.test(queryText),
        group: /(lab|laboratory|group|research)/.test(queryText),
        program: /(program|programs|degree|major|minor|certificate|graduate program|undergraduate program)/.test(queryText),
        resource: /(resource|resources|faq|help|support|policy|policies|office hours|computing|hpc|cluster|facility|facilities|advising|advisor|internship|internships|job|jobs|career|careers|scholarship|funding|financial aid)/.test(queryText),
        navigation: isNavigationQuery(queryText)
      };
    }

    function scoreItem(item, query, options) {
      const settings = options || {};
      const normalizedQuery = normalizeQuery(query);
      const cleanQuery = normalizedQuery.raw;
      const queryTokens = normalizedQuery.tokens;
      const intent = inferIntent(cleanQuery);
      const title = normalizeText(item.title);
      const courseCode = normalizeText(item.courseCode);
      const compactCourseCode = (item.courseCode || '').replace(/\s+/g, '').toLowerCase();
      const courseName = normalizeText(item.courseName);
      const personName = normalizeText(item.personName);
      const jobTitle = normalizeText(item.jobTitle);
      const compactTitle = title.replace(/\s+/g, '');
      const compactQuery = normalizedQuery.compact;
      const summary = normalizeText(item.summary);
      const slug = normalizeText(item.slug);
      const aliases = item.aliases.map(normalizeText);
      const keywords = item.keywords.map(normalizeText);
      const topics = item.relatedTopics.map(normalizeText);
      const researchAreas = item.researchAreas.map(normalizeText);
      const teachesCourses = item.teachesCourses.map(normalizeText);
      const currentTeachingTerms = item.currentTeachingTerms.map(normalizeText);
      const teachingAcademicYears = item.teachingAcademicYears.map(normalizeText);
      const externalResearchTopics = item.externalResearchTopics.map(normalizeText);
      const labOrGroup = item.labOrGroup.map(normalizeText);
      const profileLinks = item.profileLinks.map(normalizeText);
      const sourceUrls = item.sourceUrls.map(normalizeText);
      const recentNewsTitles = item.recentNewsTitles.map(normalizeText);
      const instructors = item.instructors.map(normalizeText);
      const offeringsTerms = item.offeringsTerms.map(normalizeText);
      const offeringsAcademicYears = item.offeringsAcademicYears.map(normalizeText);
      const instructorTopics = item.instructorTopics.map(normalizeText);
      const relatedPeopleNames = item.relatedPeopleNames.map(normalizeText);
      const navLabel = normalizeText(item.navLabel);
      const sectionName = normalizeText(item.sectionName);
      const parentSection = normalizeText(item.parentSection);
      const menuKeywords = item.menuKeywords.map(normalizeText);
      const relatedTopicSignals = relationMaps && item.type === 'person'
        ? toArray(relationMaps.groupTopicsByPersonId.get(item.id)).map(normalizeText)
        : [];
      const fields = [title, courseCode, courseName, personName, jobTitle, summary, slug, navLabel, sectionName, parentSection]
        .concat(
          aliases,
          keywords,
          topics,
          researchAreas,
          teachesCourses,
          currentTeachingTerms,
          teachingAcademicYears,
          externalResearchTopics,
          labOrGroup,
          profileLinks,
          sourceUrls,
          recentNewsTitles,
          instructors,
          offeringsTerms,
          offeringsAcademicYears,
          instructorTopics,
          relatedPeopleNames,
          menuKeywords,
          relatedTopicSignals
        )
        .filter(Boolean);
      const singleTokenQuery = !cleanQuery.includes(' ');
      const phraseMatched = fields.some((field) => {
        const fieldTokens = tokenizeText(field);
        return field === cleanQuery || (singleTokenQuery ? fieldTokens.includes(cleanQuery) : field.includes(cleanQuery));
      });
      const tokenHits = countTokenHits(queryTokens, fields);

      if (!phraseMatched && tokenHits === 0) {
        return 0;
      }

      if (settings.strict !== false && queryTokens.length > 1 && !phraseMatched && tokenHits < 2) {
        return 0;
      }

      let score = 0;

      if (compactCourseCode && compactCourseCode === compactQuery) {
        score += 900;
      }

      if (compactTitle === compactQuery) {
        score += 700;
      }

      score += scoreField(courseCode, cleanQuery, queryTokens, { exact: 650, partial: 280, token: 65 });
      score += scoreField(courseName, cleanQuery, queryTokens, { exact: 320, partial: 140, token: 32 });
      score += scoreField(personName, cleanQuery, queryTokens, { exact: 560, partial: 240, token: 55 });
      score += scoreField(jobTitle, cleanQuery, queryTokens, { exact: 100, partial: 50, token: 12 });
      score += scoreField(title, cleanQuery, queryTokens, { exact: 500, partial: 220, token: 50 });
      score += scoreField(slug, cleanQuery, queryTokens, { exact: 180, partial: 80, token: 20 });
      score += scoreArray(aliases, cleanQuery, queryTokens, { exact: 420, partial: 180, token: 42 });
      score += scoreArray(keywords, cleanQuery, queryTokens, { exact: 260, partial: 110, token: 30 });
      score += scoreArray(topics, cleanQuery, queryTokens, { exact: 160, partial: 70, token: 20 });
      score += scoreArray(researchAreas, cleanQuery, queryTokens, { exact: 180, partial: 90, token: 22 });
      score += scoreArray(teachesCourses, cleanQuery, queryTokens, { exact: 220, partial: 110, token: 28 });
      score += scoreArray(currentTeachingTerms, cleanQuery, queryTokens, { exact: 90, partial: 40, token: 10 });
      score += scoreArray(teachingAcademicYears, cleanQuery, queryTokens, { exact: 60, partial: 25, token: 8 });
      score += scoreArray(externalResearchTopics, cleanQuery, queryTokens, { exact: 140, partial: 60, token: 14 });
      score += scoreArray(labOrGroup, cleanQuery, queryTokens, { exact: 120, partial: 55, token: 14 });
      score += scoreArray(profileLinks, cleanQuery, queryTokens, { exact: 30, partial: 12, token: 4 });
      score += scoreArray(sourceUrls, cleanQuery, queryTokens, { exact: 10, partial: 5, token: 2 });
      score += scoreArray(recentNewsTitles, cleanQuery, queryTokens, { exact: 45, partial: 18, token: 5 });
      score += scoreArray(instructors, cleanQuery, queryTokens, { exact: 260, partial: 120, token: 35 });
      score += scoreArray(offeringsTerms, cleanQuery, queryTokens, { exact: 80, partial: 30, token: 8 });
      score += scoreArray(offeringsAcademicYears, cleanQuery, queryTokens, { exact: 70, partial: 25, token: 8 });
      score += scoreArray(instructorTopics, cleanQuery, queryTokens, { exact: 110, partial: 45, token: 12 });
      score += scoreArray(relatedPeopleNames, cleanQuery, queryTokens, { exact: 180, partial: 80, token: 20 });
      score += scoreField(navLabel, cleanQuery, queryTokens, { exact: 520, partial: 240, token: 60 });
      score += scoreField(sectionName, cleanQuery, queryTokens, { exact: 400, partial: 180, token: 45 });
      score += scoreField(parentSection, cleanQuery, queryTokens, { exact: 90, partial: 40, token: 12 });
      score += scoreArray(menuKeywords, cleanQuery, queryTokens, { exact: 340, partial: 160, token: 38 });
      score += scoreArray(relatedTopicSignals, cleanQuery, queryTokens, { exact: 120, partial: 50, token: 18 });
      score += scoreField(summary, cleanQuery, queryTokens, { exact: 120, partial: 45, token: 10 });
      score += tokenHits * 35;

      if (item.type === 'course' && /^([a-z]{2,4}\s?\d{3}[a-z]?)$/i.test(cleanQuery) && (compactTitle.includes(compactQuery) || compactCourseCode === compactQuery)) {
        score += 500;
      }

      if (item.type === 'person' && (personName === cleanQuery || aliases.includes(cleanQuery))) {
        score += 420;
      }

      if (item.type === 'person' && (externalResearchTopics.length || labOrGroup.length)) {
        score += 8;
      }

      if (intent.person && item.type === 'person') { score += 160; }
      if (intent.person && item.type === 'course' && (instructors.length || relatedPeopleNames.length)) { score += 45; }
      if (intent.person && item.type === 'group') { score += 35; }
      if (intent.course && item.type === 'course') { score += 120; }
      if (intent.group && item.type === 'group') { score += 120; }
      if (intent.program && item.type === 'program') { score += 120; }
      if (intent.program && item.type === 'course') { score -= 20; }
      if (intent.resource && item.type === 'resource') { score += 120; }
      if (intent.resource && item.type === 'facility') { score += 135; }
      if (intent.resource && item.type === 'page') { score += 40; }
      if (intent.navigation && item.isLandingPage) { score += 220; }
      if (intent.navigation && item.isLandingPage && (navLabel === cleanQuery || sectionName === cleanQuery || title === cleanQuery)) { score += 320; }
      if (intent.navigation && !item.isLandingPage && (item.type === 'person' || item.type === 'course' || item.type === 'group')) { score -= 45; }
      if (intent.navigation && item.parentSection && item.parentSection === cleanQuery) { score += 40; }

      return score;
    }

    function getRankedEntries(query, options) {
      const seenKeys = new Set();
      return searchIndex
        .map((item) => ({ item, score: scoreItem(item, query, options) }))
        .filter((entry) => entry.score > 0)
        .sort((a, b) => b.score - a.score)
        .filter((entry) => {
          const item = entry.item || {};
          const rawKey = item.url || item.permalink || item.slug || item.id || '';
          const stableKey = rawKey
            .toString()
            .trim()
            .toLowerCase()
            .replace(/\/$/, '');
          const fallbackTitleKey = normalizeText(item.title || '');
          const dedupeKey = stableKey || `title:${fallbackTitleKey}`;

          if (!dedupeKey) {
            return true;
          }

          if (seenKeys.has(dedupeKey)) {
            return false;
          }

          seenKeys.add(dedupeKey);
          return true;
        })
        .slice(0, 5);
    }

    function getRelatedFallbackEntries(query) {
      const intent = inferIntent(normalizeQuery(query).raw);
      let preferredTypes = ['resource', 'facility', 'page', 'department'];

      if (intent.course) {
        preferredTypes = ['course', 'program', 'page'];
      } else if (intent.person) {
        preferredTypes = ['person', 'page', 'resource'];
      } else if (intent.group) {
        preferredTypes = ['group', 'facility', 'resource', 'page'];
      } else if (intent.program) {
        preferredTypes = ['program', 'page', 'resource'];
      } else if (intent.resource) {
        preferredTypes = ['facility', 'resource', 'page'];
      }

      const preferred = searchIndex.filter((item) => preferredTypes.includes(item.type));
      const scoredPreferred = preferred
        .map((item) => {
          const text = normalizeText([
            item.title,
            item.summary,
            item.keywords,
            item.aliases,
            item.relatedTopics
          ]);
          const queryTokens = normalizeQuery(query).tokens;
          const tokenHits = countTokenHits(queryTokens, [text]);

          return {
            item,
            score: tokenHits * 20 + (preferredTypes.length - preferredTypes.indexOf(item.type))
          };
        })
        .sort((a, b) => b.score - a.score);

      const best = scoredPreferred.filter((entry) => entry.score > 0).slice(0, 5);
      if (best.length) {
        return {
          message: 'No exact matches found; showing related results.',
          items: best.map((entry) => entry.item)
        };
      }

      return {
        message: 'No exact matches found; showing useful department pages.',
        items: preferred.slice(0, 5)
      };
    }

    function renderDebugPanel() {
      if (!isDebugMode() || !searchIndex) {
        debugNode.hidden = true;
        debugNode.innerHTML = '';
        return;
      }

      const sections = debugQueries.map((query) => {
        const strictRanked = getRankedEntries(query, { strict: true });
        const ranked = strictRanked.length ? strictRanked : getRankedEntries(query, { strict: false });

        return `
          <section>
            <h3><code>${escapeHtml(query)}</code></h3>
            <ul>
              ${ranked.length ? ranked.map((entry) => `
                <li>
                  <strong>${escapeHtml(entry.item.title)}</strong>
                  (${escapeHtml(getEntityLabel(entry.item.type))}, score ${entry.score})
                </li>
              `).join('') : '<li>No matches</li>'}
            </ul>
          </section>
        `;
      }).join('');

      debugNode.hidden = false;
      debugNode.innerHTML = `
        <h2>Retrieval Debug</h2>
        <p>Representative queries are shown below with top matches and scores. Open the browser console for detailed tables.</p>
        ${sections}
      `;

      console.groupCollapsed('AI assistant retrieval debug');
      debugQueries.forEach((query) => {
        const strictRanked = getRankedEntries(query, { strict: true });
        const ranked = strictRanked.length ? strictRanked : getRankedEntries(query, { strict: false });
        console.group(`Query: ${query}`);
        console.table(ranked.map((entry) => ({
          score: entry.score,
          type: getEntityLabel(entry.item.type),
          title: entry.item.title,
          url: entry.item.url,
          summary: entry.item.summary
        })));
        console.groupEnd();
      });
      console.groupEnd();
    }

    function getSectionRelatedItems(landingItem, results) {
      if (!landingItem || !landingItem.isLandingPage) {
        return [];
      }

      const sectionKey = normalizeText(landingItem.sectionName || landingItem.navLabel || landingItem.title);
      if (!sectionKey) {
        return [];
      }

      return results.filter((item) => {
        if (item.id === landingItem.id) {
          return false;
        }

        return normalizeText(item.parentSection) === sectionKey;
      }).slice(0, 4);
    }

    function renderResultCard(item, relatedItems) {
      const explanation = buildExplanation(item);
      const itemLabel = getEntityLabel(item.type);
      const metaParts = [];
      const itemUrl = sanitizeEntityUrl(item.url);
      const safeRelatedItems = relatedItems || [];

      const relatedMarkup = safeRelatedItems.length ? `
        <div class="ai-assistant-related">
          <h4>Related pages</h4>
          <ul>
            ${safeRelatedItems.map((relatedItem) => {
              const relatedUrl = sanitizeEntityUrl(relatedItem.url);
              const relatedLabel = getEntityLabel(relatedItem.type);
              return relatedUrl
                ? `<li><a href="${escapeHtml(relatedUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(relatedItem.title)}</a> <span>(${escapeHtml(relatedLabel)})</span></li>`
                : `<li>${escapeHtml(relatedItem.title)} <span>(${escapeHtml(relatedLabel)})</span></li>`;
            }).join('')}
          </ul>
        </div>
      ` : '';

      if (!itemUrl) {
        return `
          <article class="ai-assistant-result">
            <div class="ai-assistant-result-header">
              <h3>${escapeHtml(item.title)}</h3>
              <span class="ai-assistant-type ${escapeHtml(getEntityTypeClass(item.type))}">${escapeHtml(itemLabel)}</span>
            </div>
            ${metaParts.length ? `<p class="ai-assistant-meta">${escapeHtml(metaParts.join(' • '))}</p>` : ''}
            <p class="ai-assistant-explanation">${escapeHtml(explanation)}</p>
            ${relatedMarkup}
          </article>
        `;
      }

      return `
        <article class="ai-assistant-result">
          <div class="ai-assistant-result-header">
            <h3><a href="${escapeHtml(itemUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title)}</a></h3>
            <span class="ai-assistant-type ${escapeHtml(getEntityTypeClass(item.type))}">${escapeHtml(itemLabel)}</span>
          </div>
          ${metaParts.length ? `<p class="ai-assistant-meta">${escapeHtml(metaParts.join(' • '))}</p>` : ''}
          <p class="ai-assistant-explanation">${escapeHtml(explanation)}</p>
          ${relatedMarkup}
          <a class="ai-assistant-link" href="${escapeHtml(itemUrl)}" target="_blank" rel="noopener noreferrer">Open ${escapeHtml(itemLabel.toLowerCase())}</a>
        </article>
      `;
    }

    function renderResults(results, statusMessage, query) {
      if (!results.length) {
        resultsNode.innerHTML = '';
        statusNode.textContent = statusMessage || 'No strong matches were found. Try a course code, a faculty name, a program name, a group, or a simpler keyword.';
        return;
      }

      statusNode.textContent = statusMessage || 'Top matches:';
      const navigationQuery = isNavigationQuery(query || '');
      const topItem = results[0];
      const relatedItems = navigationQuery && topItem && topItem.isLandingPage
        ? getSectionRelatedItems(topItem, results)
        : [];
      const relatedIds = new Set(relatedItems.map((item) => item.id));
      const remainingResults = navigationQuery && topItem && topItem.isLandingPage
        ? [topItem].concat(results.slice(1).filter((item) => !relatedIds.has(item.id)))
        : results;

      resultsNode.innerHTML = remainingResults.map((item, index) => {
        const sectionRelatedItems = index === 0 ? relatedItems : [];
        return renderResultCard(item, sectionRelatedItems);
      }).join('');
    }

    function renderAssistantAnswer(responseText) {
      if (!responseText) {
        answerNode.hidden = true;
        answerNode.innerHTML = '';
        return;
      }

      answerNode.hidden = false;
      answerNode.innerHTML = `<div>${escapeHtml(responseText).replace(/\n/g, '<br>')}</div>`;
    }

    function renderFallbackMessage() {
      answerNode.hidden = true;
      answerNode.innerHTML = '';
    }

    function getSlmConfig() {
      if (!window.csDepartmentAssistantSlmConfig) {
        return null;
      }

      const config = window.csDepartmentAssistantSlmConfig;
      if (!config.endpoint || !config.model) {
        return null;
      }

      return {
        endpoint: config.endpoint,
        model: config.model,
        apiKey: config.apiKey || '',
        headers: config.headers || {},
        temperature: typeof config.temperature === 'number' ? config.temperature : 0.2,
        maxTokens: typeof config.maxTokens === 'number' ? config.maxTokens : 220
      };
    }

    async function requestSlmCompletion(promptPayload) {
      const slmConfig = getSlmConfig();
      if (!slmConfig) {
        return null;
      }

      const headers = Object.assign(
        {
          'Content-Type': 'application/json'
        },
        slmConfig.headers
      );

      if (slmConfig.apiKey) {
        headers.Authorization = `Bearer ${slmConfig.apiKey}`;
      }

      const response = await fetch(slmConfig.endpoint, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          model: slmConfig.model,
          temperature: slmConfig.temperature,
          max_tokens: slmConfig.maxTokens,
          messages: promptPayload.messages
        })
      });

      if (!response.ok) {
        throw new Error('SLM request failed.');
      }

      const data = await response.json();
      const content = data
        && data.choices
        && data.choices[0]
        && data.choices[0].message
        && data.choices[0].message.content;

      return typeof content === 'string' ? content.trim() : null;
    }

    async function requestGroundedAnswer(promptPayload) {
      window.csAssistantLastPromptPayload = promptPayload;

      try {
        if (window.csDepartmentAssistantLlm && typeof window.csDepartmentAssistantLlm.complete === 'function') {
          return await window.csDepartmentAssistantLlm.complete({
            query: promptPayload.query,
            messages: promptPayload.messages,
            entities: promptPayload.entities
          });
        }

        return await requestSlmCompletion(promptPayload);
      } catch (error) {
        return null;
      }
    }

    async function performSearch() {
      const query = queryInput.value.trim();

      if (!query) {
        statusNode.textContent = 'Search courses, faculty, programs, groups, and resources.';
        renderAssistantAnswer('');
        resultsNode.innerHTML = '';
        return;
      }

      if (!searchIndex) {
        statusNode.textContent = 'Search data is still loading. Please try again in a moment.';
        return;
      }

      let ranked = getRankedEntries(query, { strict: true }).map((entry) => entry.item);
      let statusMessage = 'Top matches:';

      if (!ranked.length) {
        ranked = getRankedEntries(query, { strict: false }).map((entry) => entry.item);
      }

      if (!ranked.length) {
        const fallback = getRelatedFallbackEntries(query);
        ranked = fallback.items;
        statusMessage = fallback.message;
      }

      const promptPayload = buildPromptPayload(query, ranked);
      const assistantResponse = await requestGroundedAnswer(promptPayload);
      if (assistantResponse) {
        renderAssistantAnswer(assistantResponse);
      } else {
        renderFallbackMessage();
      }
      renderResults(ranked, statusMessage, query);
    }

    statusNode.textContent = 'Loading search index...';

    fetch(dataUrl)
      .then((response) => {
        if (!response.ok) {
          throw new Error('Failed to load search index.');
        }
        return response.json();
      })
      .then((data) => {
        searchIndex = buildIndex(data);
        relationMaps = buildRelationMaps(searchIndex);
        statusNode.textContent = 'Search courses, faculty, programs, groups, and resources.';
        renderDebugPanel();
      })
      .catch(() => {
        statusNode.textContent = 'The search index could not be loaded right now. Please try again later.';
      });

    searchButton.addEventListener('click', function() {
      performSearch();
    });
    queryInput.addEventListener('keydown', function(event) {
      if (event.key === 'Enter') {
        performSearch();
      }
    });
  })();
</script>
