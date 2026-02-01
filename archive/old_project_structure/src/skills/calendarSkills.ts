/**
 * Represents a summary of a calendar event.
 * This structure will need to be defined based on the actual data available
 * from the calendar API and the needs of the Proactive Meeting Prep Assistant.
 */
export interface CalendarEventSummary {
  id: string;
  title: string;
  startTime: Date;
  endTime: Date;
  description?: string;
  attendees?: string[]; // e.g., list of email addresses or names
  location?: string;
  organizer?: string;
  // Potentially other relevant fields like meeting link, etc.
}

const STOP_WORDS: string[] = [
  'a',
  'an',
  'and',
  'are',
  'as',
  'at',
  'be',
  'but',
  'by',
  'for',
  'if',
  'in',
  'into',
  'is',
  'it',
  'its',
  'my',
  'no',
  'not',
  'of',
  'on',
  'or',
  'such',
  'that',
  'the',
  'their',
  'then',
  'there',
  'these',
  'they',
  'this',
  'to',
  'was',
  'will',
  'with',
  'i',
  'me',
  'you',
  'he',
  'she',
  'we',
  'us',
  'am',
  'pm', // also time indicators if not handled by date parser
];

/**
 * Generates n-grams (specifically bigrams) from a string.
 * @param str The input string.
 * @param n The size of the n-grams (default is 2 for bigrams).
 * @returns An array of n-grams.
 */
function _getNgrams(str: string, n: number = 2): string[] {
  const cleanedStr = str.toLowerCase().replace(/[^a-z0-9]/g, ''); // Keep only alphanumeric for n-grams
  if (cleanedStr.length < n) {
    return [];
  }
  const ngrams: string[] = [];
  for (let i = 0; i <= cleanedStr.length - n; i++) {
    ngrams.push(cleanedStr.substring(i, i + n));
  }
  return ngrams;
}

/**
 * Calculates string similarity based on n-gram comparison (Sørensen-Dice coefficient).
 * @param str1 First string.
 * @param str2 Second string.
 * @param n N-gram size (default 2 for bigrams).
 * @returns Similarity score between 0 and 1.
 */
function getStringSimilarity(
  str1: string,
  str2: string,
  n: number = 2
): number {
  if (!str1 || !str2) {
    return 0;
  }
  // Normalize strings for comparison beyond just n-gram generation (e.g. full string if short)
  const s1 = str1.toLowerCase().replace(/\s+/g, '');
  const s2 = str2.toLowerCase().replace(/\s+/g, '');

  if (s1 === s2) {
    // Exact match after normalization
    return 1.0;
  }

  const ngrams1 = _getNgrams(s1, n);
  const ngrams2 = _getNgrams(s2, n);

  if (ngrams1.length === 0 || ngrams2.length === 0) {
    return 0;
  }

  const set1 = new Set(ngrams1);
  const set2 = new Set(ngrams2);
  let commonCount = 0;

  for (const ngram of set1) {
    if (set2.has(ngram)) {
      // For actual Dice, you'd count occurrences in lists, not just presence in sets,
      // if strings can have repeated n-grams. For simplicity with sets:
      commonCount++;
    }
  }
  // Simplified Dice for sets: (2 * |Intersection|) / (|Set1| + |Set2|)
  // More accurate Dice for bags (multisets) of ngrams: (2 * commonNgramsCount) / (ngrams1.length + ngrams2.length)
  // Let's do the more accurate one by iterating through one list and removing from a copy of the other.

  commonCount = 0;
  const ngrams2Copy = [...ngrams2];
  for (const ngram of ngrams1) {
    const indexInCopy = ngrams2Copy.indexOf(ngram);
    if (indexInCopy !== -1) {
      commonCount++;
      ngrams2Copy.splice(indexInCopy, 1); // Remove to handle duplicates correctly
    }
  }

  return (2 * commonCount) / (ngrams1.length + ngrams2.length);
}

/**
 * Extracts a display name from a typical calendar attendee string.
 * @param attendeeString The raw attendee string (e.g., "John Doe <john.doe@example.com>", "jane@example.com").
 * @returns A lowercase, cleaned name part or an empty string.
 */
function _extractNameFromAttendeeString(attendeeString: string): string {
  if (!attendeeString) return '';

  attendeeString = attendeeString.toLowerCase();

  // Case 1: "FullName <email>" or "FirstName <email>"
  const emailMatch = attendeeString.match(/^(.*?)<.*>$/);
  if (emailMatch && emailMatch[1]) {
    return emailMatch[1].trim();
  }

  // Case 2: "Name (Guest)" or "Name (External)"
  const guestMatch = attendeeString.match(/^(.*?)\s*\((guest|external)\)/);
  if (guestMatch && guestMatch[1]) {
    return guestMatch[1].trim();
  }

  // Case 3: Just an email "user@example.com" -> "user"
  if (attendeeString.includes('@')) {
    const parts = attendeeString.split('@');
    // Further clean username part if it contains dots or numbers that are not part of typical first/last names
    // For simplicity here, just taking the part before @. More sophisticated cleaning could be added.
    return parts[0].replace(/[^a-z\s'-]/gi, '').trim(); // Keep letters, spaces, hyphens, apostrophes
  }

  // Case 4: Just a name (no email, no guest marker)
  // Clean it similarly to the email username part
  return attendeeString.replace(/[^a-z\s'-]/gi, '').trim();
}

/**
 * Optional date hints to narrow down the search for a calendar event.
 * - specificDate: Looks for events on this particular day.
 * - startDate/endDate: Defines a window to search for events.
 * If multiple hints are provided, the narrowest possible range should be prioritized.
 * For example, if specificDate is given, startDate and endDate might be ignored or used as validation.
 */
export interface DateHints {
  specificDate?: Date; // e.g., "find my meeting on 2024-03-15"
  startDate?: Date; // e.g., "my meeting sometime after next Monday"
  endDate?: Date; // e.g., "my meeting before the end of next week"
}

/**
 * Finds a calendar event based on a natural language reference and optional date hints.
 *
 * @param userId The ID of the user whose calendar is to be searched.
 * @param meeting_reference A natural language string describing the meeting
 *                          (e.g., "my sync up tomorrow", "budget review next week").
 * @param date_hints Optional hints to narrow down the date range for the search.
 * @returns A Promise that resolves to a CalendarEventSummary if a suitable event
 *          is found, or undefined otherwise.
 */
export async function findCalendarEventByFuzzyReference(
  userId: string,
  meeting_reference: string,
  date_hints?: DateHints
): Promise<CalendarEventSummary | undefined> {
  console.log(
    `[findCalendarEventByFuzzyReference] Inputs: userId=${userId}, reference="${meeting_reference}", hints=${JSON.stringify(date_hints)}`
  );

  // 1. Determine search window based on date_hints or defaults.
  let searchWindowStart: Date;
  let searchWindowEnd: Date;
  const now = new Date();

  if (date_hints?.specificDate) {
    searchWindowStart = new Date(date_hints.specificDate);
    searchWindowStart.setHours(0, 0, 0, 0); // Start of the day
    searchWindowEnd = new Date(date_hints.specificDate);
    searchWindowEnd.setHours(23, 59, 59, 999); // End of the day
  } else if (date_hints?.startDate && date_hints?.endDate) {
    searchWindowStart = new Date(date_hints.startDate);
    searchWindowEnd = new Date(date_hints.endDate);
  } else if (date_hints?.startDate) {
    searchWindowStart = new Date(date_hints.startDate);
    searchWindowEnd = new Date(searchWindowStart);
    searchWindowEnd.setDate(searchWindowStart.getDate() + 14); // Default 2 weeks window
    searchWindowEnd.setHours(23, 59, 59, 999);
  } else if (date_hints?.endDate) {
    searchWindowEnd = new Date(date_hints.endDate);
    searchWindowStart = new Date(searchWindowEnd);
    searchWindowStart.setDate(searchWindowEnd.getDate() - 14); // Default 2 weeks window prior
    searchWindowStart.setHours(0, 0, 0, 0);
  } else {
    // Default search window: from start of today to 14 days in the future
    searchWindowStart = new Date(now);
    searchWindowStart.setHours(0, 0, 0, 0);
    searchWindowEnd = new Date(now);
    searchWindowEnd.setDate(now.getDate() + 14);
    searchWindowEnd.setHours(23, 59, 59, 999);
  }

  console.log(
    `[findCalendarEventByFuzzyReference] Determined search window: ${searchWindowStart.toISOString()} to ${searchWindowEnd.toISOString()}`
  );

  // 2. Fetch calendar events for the user within that window (mocked for now).
  const mockEvents = await mockFetchUserCalendarEvents(
    userId,
    searchWindowStart,
    searchWindowEnd
  );
  console.log(
    `[findCalendarEventByFuzzyReference] Fetched ${mockEvents.length} mock events.`
  );

  // 3. Apply matching logic (fuzzy, keyword, or LLM-based) against meeting_reference.
  if (mockEvents.length === 0) {
    console.log(
      '[findCalendarEventByFuzzyReference] No mock events found in the search window. Returning undefined.'
    );
    return undefined;
  }

  const meetingReferenceLower = meeting_reference.toLowerCase();

  // Enhanced keyword extraction:
  // 1. Split by non-alphanumeric characters (handles punctuation better than just space)
  // 2. Filter out stop words
  // 3. Filter out very short words (e.g., < 3 chars)
  const rawWords = meetingReferenceLower.split(/[^a-z0-9]+/).filter(Boolean); // Split and remove empty strings
  const keywords = rawWords.filter(
    (word) => !STOP_WORDS.includes(word) && word.length >= 3
  );

  if (keywords.length === 0 && rawWords.length > 0) {
    // If all words were stop words or too short, fall back to using all short words from original reference
    // to catch cases like "1:1" or if the meeting title itself is very short and like a stop word.
    console.log(
      '[findCalendarEventByFuzzyReference] No significant keywords after filtering, falling back to raw short words if any.'
    );
    keywords.push(
      ...rawWords.filter((word) => word.length > 0 && word.length < 3)
    ); // Add back very short words
    if (keywords.length === 0) {
      // If still nothing, use all raw words
      keywords.push(...rawWords);
    }
    console.log(
      `[findCalendarEventByFuzzyReference] Fallback keywords: ${keywords.join(', ')}`
    );
  }

  console.log(
    `[findCalendarEventByFuzzyReference] Processed Keywords from reference: ${keywords.join(', ')}`
  );
  const processedReference = keywords.join(' '); // Use this for overall similarity

  let bestMatch: CalendarEventSummary | undefined = undefined;
  let highestScore = 0.0; // Scores are now float (0.0 to 1.0+)

  for (const event of mockEvents) {
    const eventTitleLower = event.title.toLowerCase();
    const eventDescriptionLower = event.description?.toLowerCase() || '';

    // Primary score from fuzzy matching the processed reference against the event title
    let currentScore = getStringSimilarity(processedReference, eventTitleLower);
    // console.log(`[findCalendarEventByFuzzyReference] Event: "${event.title}", Initial Similarity Score: ${currentScore.toFixed(3)}`);

    // Bonus for exact keyword matches in title
    let titleBonus = 0;
    for (const keyword of keywords) {
      if (eventTitleLower.includes(keyword)) {
        titleBonus += 0.05; // Small bonus for each keyword found in title
      }
    }
    // Cap title bonus to avoid over-inflation by many small keywords
    currentScore += Math.min(titleBonus, 0.25);

    // Bonus for exact keyword matches in description (smaller bonus)
    let descriptionBonus = 0;
    for (const keyword of keywords) {
      if (eventDescriptionLower.includes(keyword)) {
        descriptionBonus += 0.025;
      }
    }
    currentScore += Math.min(descriptionBonus, 0.1);

    // Attendee matching bonus
    let attendeeMatchBonus = 0;
    const maxAttendeeBonus = 0.3; // Max possible bonus from attendees
    if (event.attendees && event.attendees.length > 0) {
      const matchedKeywordsInAttendees = new Set<string>(); // Track keywords that already gave a bonus for this event
      for (const attendeeString of event.attendees) {
        const eventAttendeeName =
          _extractNameFromAttendeeString(attendeeString);
        if (eventAttendeeName) {
          for (const keyword of keywords) {
            // Avoid re-scoring the same keyword if it matched another attendee for this event already
            if (matchedKeywordsInAttendees.has(keyword)) continue;

            const nameSimilarity = getStringSimilarity(
              keyword,
              eventAttendeeName
            );
            if (nameSimilarity > 0.7) {
              // High threshold for name match
              attendeeMatchBonus += 0.15; // Significant bonus for a good name match
              matchedKeywordsInAttendees.add(keyword); // Mark this keyword as used for attendee bonus for this event
              // console.log(`[findCalendarEventByFuzzyReference] Attendee match: keyword "${keyword}" vs attendee "${eventAttendeeName}", similarity ${nameSimilarity.toFixed(3)}`);
            }
          }
        }
      }
    }
    currentScore += Math.min(attendeeMatchBonus, maxAttendeeBonus); // Cap attendee bonus

    console.log(
      `[findCalendarEventByFuzzyReference] Event: "${event.title}", Similarity: ${getStringSimilarity(processedReference, eventTitleLower).toFixed(3)}, TitleBonus: ${titleBonus.toFixed(3)}, DescBonus: ${descriptionBonus.toFixed(3)}, AttendeeBonus: ${attendeeMatchBonus.toFixed(3)}, Final Score: ${currentScore.toFixed(3)}`
    );

    if (currentScore > highestScore) {
      highestScore = currentScore;
      bestMatch = event;
    } else if (currentScore === highestScore && currentScore > 0.01) {
      // Check currentScore > 0.01 to avoid tie-breaking on zero scores
      // If scores are tied, prefer the one that starts sooner
      if (bestMatch && event.startTime < bestMatch.startTime) {
        console.log(
          `[findCalendarEventByFuzzyReference] Tied score, preferring earlier event: "${event.title}" over "${bestMatch.title}"`
        );
        bestMatch = event;
      }
    }
  }

  // Adjust minimum score threshold for similarity scores (0.0 to 1.0 range)
  const minimumScoreThreshold = 0.3;
  if (bestMatch && highestScore >= minimumScoreThreshold) {
    console.log(
      `[findCalendarEventByFuzzyReference] Best match found: "${bestMatch.title}" with score ${highestScore.toFixed(3)} (Threshold: ${minimumScoreThreshold})`
    );
    return bestMatch;
  } else {
    if (bestMatch) {
      // A best match was found, but it didn't meet the threshold
      console.log(
        `[findCalendarEventByFuzzyReference] A potential match "${bestMatch.title}" was found with score ${highestScore.toFixed(3)}, but it's below the threshold of ${minimumScoreThreshold}.`
      );
    } else {
      // No events scored > 0 or no events at all after filtering
      console.log(
        `[findCalendarEventByFuzzyReference] No event scored above 0 or no events to score.`
      );
    }
    console.log(
      `[findCalendarEventByFuzzyReference] No event met the minimum score threshold (${minimumScoreThreshold}).`
    );
    return undefined;
  }
}

// Helper function to mock fetching calendar events
async function mockFetchUserCalendarEvents(
  userId: string,
  startDate: Date,
  endDate: Date
): Promise<CalendarEventSummary[]> {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()); // Midnight today

  const sampleEvents: CalendarEventSummary[] = [
    {
      id: 'evt1',
      title: 'Project Phoenix Sync-Up',
      startTime: new Date(new Date(today).setDate(today.getDate() + 1)),
      endTime: new Date(new Date(today).setDate(today.getDate() + 1)),
      description: 'Weekly sync for Project Phoenix.',
      attendees: [
        'currentUser@example.com',
        'Mark Johnson <mark.j@example.com>',
        'team.member.jane@example.com',
      ],
      organizer: 'mark.j@example.com',
    },
    {
      id: 'evt2',
      title: 'Marketing Strategy Meeting',
      startTime: new Date(new Date(today).setDate(today.getDate() + 2)),
      endTime: new Date(new Date(today).setDate(today.getDate() + 2)),
      description: 'Discuss Q3 marketing strategy with Alice and the team.',
      attendees: [
        'currentUser@example.com',
        'Alice Wonderland <alice.w@example.com>',
        'marketing_lead@example.com',
        'Bob (Guest)',
      ],
      location: 'Conference Room B',
      organizer: 'marketing_lead@example.com',
    },
    {
      id: 'evt3',
      title: '1:1 with Sarah Miller', // More specific title
      startTime: new Date(new Date(today).setDate(today.getDate() + 3)),
      endTime: new Date(new Date(today).setDate(today.getDate() + 3)),
      attendees: ['currentUser@example.com', 'Sarah Miller <sarahm@corp.com>'], // Specific manager name
      organizer: 'sarahm@corp.com',
    },
    {
      id: 'evt4',
      title: 'Team Lunch',
      startTime: new Date(new Date(today).setDate(today.getDate() + 7)),
      endTime: new Date(new Date(today).setDate(today.getDate() + 7)),
      description: 'Casual team lunch at The Eatery.',
      attendees: [
        'currentUser@example.com',
        'Mark Johnson <mark.j@example.com>',
        'team.member.jane@example.com',
        'Alice Wonderland <alice.w@example.com>',
      ],
      location: 'The Eatery',
      organizer: 'currentUser@example.com',
    },
    {
      id: 'evt5',
      title: 'Budget Review Q2',
      startTime: new Date(new Date(today).setDate(today.getDate() - 7)),
      endTime: new Date(new Date(today).setDate(today.getDate() - 7)),
      description: 'Final review of Q2 budget.',
      attendees: [
        'currentUser@example.com',
        'finance_dept@example.com',
        'Sarah Miller <sarahm@corp.com>',
      ],
      organizer: 'finance_dept@example.com',
    },
    {
      id: 'evt6',
      title: 'Project Phoenix - Critical Path Discussion',
      startTime: new Date(new Date(today).setDate(today.getDate() + 1)),
      endTime: new Date(new Date(today).setDate(today.getDate() + 1)),
      description: 'Urgent discussion on Project Phoenix blockers with Mark.',
      attendees: [
        'currentUser@example.com',
        'Mark Johnson <mark.j@example.com>',
        'cto@example.com',
      ],
      organizer: 'cto@example.com',
    },
    {
      // New event for attendee matching
      id: 'evt7',
      title: 'Planning Session',
      startTime: new Date(new Date(today).setDate(today.getDate() + 4)), // 4 days from now 10 AM
      endTime: new Date(new Date(today).setDate(today.getDate() + 4)), // 4 days from now 12 PM
      description: 'General planning meeting.',
      attendees: [
        'currentUser@example.com',
        'Alice Wonderland <alice.w@example.com>',
        'Bob The Builder <bob@build.it>',
        'Charlie <charlie.doe@email.com>',
      ],
      organizer: 'currentUser@example.com',
    },
  ];

  // Adjust fixed times for sample events to be relative to 'today' for consistent testing
  sampleEvents.forEach((event) => {
    if (event.id === 'evt1') {
      event.startTime.setHours(9, 0, 0, 0);
      event.endTime.setHours(10, 0, 0, 0); // Tomorrow 9 AM
    } else if (event.id === 'evt2') {
      event.startTime.setHours(14, 0, 0, 0);
      event.endTime.setHours(15, 0, 0, 0); // Day after tomorrow 2 PM
    } else if (event.id === 'evt3') {
      event.startTime.setHours(11, 0, 0, 0);
      event.endTime.setHours(11, 30, 0, 0); // 3 days from now 11 AM
    } else if (event.id === 'evt4') {
      event.startTime.setHours(12, 0, 0, 0);
      event.endTime.setHours(13, 0, 0, 0); // Next week 12 PM
    } else if (event.id === 'evt5') {
      event.startTime.setHours(15, 0, 0, 0);
      event.endTime.setHours(16, 0, 0, 0); // Last week 3 PM
    } else if (event.id === 'evt6') {
      event.startTime.setHours(14, 0, 0, 0);
      event.endTime.setHours(15, 0, 0, 0); // Tomorrow 2 PM
    } else if (event.id === 'evt7') {
      event.startTime.setHours(10, 0, 0, 0);
      event.endTime.setHours(12, 0, 0, 0); // 4 days from now 10 AM
    }
  });

  console.log(
    `[mockFetchUserCalendarEvents] Mock UserID: ${userId}. Filtering events between ${startDate.toISOString()} and ${endDate.toISOString()}`
  );

  const filteredEvents = sampleEvents.filter((event) => {
    return event.startTime >= startDate && event.startTime <= endDate;
  });

  console.log(
    `[mockFetchUserCalendarEvents] Returning ${filteredEvents.length} mock events after filtering.`
  );
  return Promise.resolve(filteredEvents);
}
