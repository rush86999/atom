import { Request, Response } from 'express';

// OpenSearch-related imports removed
// import { listRepositoriesInSearch, listSnapshotsOfRepositoryOfSearchData, restoreSnapshotInSearch, deleteIndexInSearch, createTrainEventIndexInOpenSearch, createAllEventIndexInOpenSearch, getVectorInAllEventIndexInOpenSearch, putDataInTrainEventIndexInOpenSearch, deleteDocInTrainEventIndexInOpenSearch, updateDocInTrainEventIndexInOpenSearch, convertEventTitleToOpenAIVector, searchTrainEventIndexInOpenSearch, getVectorInTrainEventIndexInOpenSearch } from '@events_search/_libs/api-helper'

// dayjs and utc are no longer needed as the function body is replaced
// import dayjs from 'dayjs'
// import utc from 'dayjs/plugin/utc'
// dayjs.extend(utc)

const opensearch = async (req: Request, res: Response) => {
  // The entire logic of this service is being deprecated.
  // All OpenSearch related operations are removed.
  return res.status(410).json({
    message:
      'This OpenSearch event search service is deprecated and no longer operational. Please use the new LanceDB-based event matching service.',
  });
};

export default opensearch;
