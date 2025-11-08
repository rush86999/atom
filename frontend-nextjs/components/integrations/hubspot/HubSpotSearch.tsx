import React, { useState, useMemo, useCallback } from "react";
import {
  Box,
  Input,
  VStack,
  HStack,
  Text,
  Badge,
  Select,
  Button,
  Checkbox,
  CheckboxGroup,
  Grid,
  GridItem,
  Spinner,
  InputGroup,
  InputLeftElement,
  Divider,
  useColorModeValue,
  Tag,
  TagLabel,
  TagCloseButton,
  Flex,
  Icon,
  Tooltip,
} from "@chakra-ui/react";
import { SearchIcon, CloseIcon } from "@chakra-ui/icons";
import { FiFilter } from "react-icons/fi";

export interface HubSpotContact {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  company: string;
  phone: string;
  lifecycleStage: string;
  leadStatus: string;
  leadScore: number;
  lastActivityDate: string;
  createdDate: string;
  owner: string;
  industry: string;
  country: string;
}

export interface HubSpotCompany {
  id: string;
  name: string;
  domain: string;
  industry: string;
  size: string;
  country: string;
  city: string;
  annualRevenue: number;
  owner: string;
  lastActivityDate: string;
  createdDate: string;
  dealStage: string;
}

export interface HubSpotDeal {
  id: string;
  name: string;
  amount: number;
  stage: string;
  closeDate: string;
  createdDate: string;
  owner: string;
  company: string;
  contact: string;
  probability: number;
  pipeline: string;
}

export interface HubSpotActivity {
  id: string;
  type: string;
  subject: string;
  body: string;
  timestamp: string;
  contact: string;
  company: string;
  owner: string;
  engagementType: string;
}

export type HubSpotDataType =
  | "contacts"
  | "companies"
  | "deals"
  | "activities"
  | "all";

export interface SearchFilters {
  searchQuery: string;
  dataType: HubSpotDataType;
  industries: string[];
  countries: string[];
  lifecycleStages: string[];
  dealStages: string[];
  leadScores: number[];
  dateRange: {
    start: string;
    end: string;
  };
  owners: string[];
  companySizes: string[];
  minRevenue: number;
  maxRevenue: number;
  minDealAmount: number;
  maxDealAmount: number;
  activityTypes: string[];
}

export interface SortOptions {
  field: string;
  direction: "asc" | "desc";
}

interface HubSpotSearchProps {
  data: (HubSpotContact | HubSpotCompany | HubSpotDeal | HubSpotActivity)[];
  dataType: HubSpotDataType;
  onSearch: (results: any[], filters: SearchFilters, sort: SortOptions) => void;
  loading?: boolean;
  totalCount?: number;
}

const HubSpotSearch: React.FC<HubSpotSearchProps> = ({
  data,
  dataType,
  onSearch,
  loading = false,
  totalCount = 0,
}) => {
  const [filters, setFilters] = useState<SearchFilters>({
    searchQuery: "",
    dataType: dataType,
    industries: [],
    countries: [],
    lifecycleStages: [],
    dealStages: [],
    leadScores: [],
    dateRange: { start: "", end: "" },
    owners: [],
    companySizes: [],
    minRevenue: 0,
    maxRevenue: 10000000,
    minDealAmount: 0,
    maxDealAmount: 10000000,
    activityTypes: [],
  });

  const [sort, setSort] = useState<SortOptions>({
    field: "lastActivityDate",
    direction: "desc",
  });

  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);

  // Extract unique values for filter options
  const filterOptions = useMemo(() => {
    const industries = new Set<string>();
    const countries = new Set<string>();
    const lifecycleStages = new Set<string>();
    const dealStages = new Set<string>();
    const owners = new Set<string>();
    const companySizes = new Set<string>();
    const activityTypes = new Set<string>();

    data.forEach((item) => {
      if ("industry" in item && item.industry) industries.add(item.industry);
      if ("country" in item && item.country) countries.add(item.country);
      if ("lifecycleStage" in item && item.lifecycleStage)
        lifecycleStages.add(item.lifecycleStage);
      if ("stage" in item && item.stage) dealStages.add(item.stage);
      if ("owner" in item && item.owner) owners.add(item.owner);
      if ("size" in item && item.size) companySizes.add(item.size);
      if ("engagementType" in item && item.engagementType)
        activityTypes.add(item.engagementType);
    });

    return {
      industries: Array.from(industries).sort(),
      countries: Array.from(countries).sort(),
      lifecycleStages: Array.from(lifecycleStages).sort(),
      dealStages: Array.from(dealStages).sort(),
      owners: Array.from(owners).sort(),
      companySizes: Array.from(companySizes).sort(),
      activityTypes: Array.from(activityTypes).sort(),
    };
  }, [data]);

  // Filter and sort data based on current filters and sort options
  const filteredData = useMemo(() => {
    let filtered = data.filter((item) => {
      // Text search across all relevant fields
      const searchLower = filters.searchQuery.toLowerCase();
      const matchesSearch =
        !filters.searchQuery ||
        ("firstName" in item &&
          item.firstName?.toLowerCase().includes(searchLower)) ||
        ("lastName" in item &&
          item.lastName?.toLowerCase().includes(searchLower)) ||
        ("email" in item && item.email?.toLowerCase().includes(searchLower)) ||
        ("company" in item &&
          item.company?.toLowerCase().includes(searchLower)) ||
        ("lastName" in item &&
          item.lastName?.toLowerCase().includes(searchLower)) ||
        ("subject" in item &&
          item.subject?.toLowerCase().includes(searchLower)) ||
        ("body" in item && item.body?.toLowerCase().includes(searchLower));

      // Data type filtering
      const matchesDataType =
        filters.dataType === "all" ||
        (filters.dataType === "contacts" && "firstName" in item) ||
        (filters.dataType === "companies" &&
          "name" in item &&
          !("firstName" in item)) ||
        (filters.dataType === "deals" && "stage" in item) ||
        (filters.dataType === "activities" && "engagementType" in item);

      // Industry filter
      const matchesIndustry =
        filters.industries.length === 0 ||
        ("industry" in item && filters.industries.includes(item.industry));

      // Country filter
      const matchesCountry =
        filters.countries.length === 0 ||
        ("country" in item && filters.countries.includes(item.country));

      // Lifecycle stage filter
      const matchesLifecycleStage =
        filters.lifecycleStages.length === 0 ||
        ("lifecycleStage" in item &&
          filters.lifecycleStages.includes(item.lifecycleStage));

      // Deal stage filter
      const matchesDealStage =
        filters.dealStages.length === 0 ||
        ("stage" in item && filters.dealStages.includes(item.stage));

      // Owner filter
      const matchesOwner =
        filters.owners.length === 0 ||
        ("owner" in item && filters.owners.includes(item.owner));

      // Company size filter
      const matchesCompanySize =
        filters.companySizes.length === 0 ||
        ("size" in item && filters.companySizes.includes(item.size));

      // Activity type filter
      const matchesActivityType =
        filters.activityTypes.length === 0 ||
        ("engagementType" in item &&
          filters.activityTypes.includes(item.engagementType));

      // Revenue range filter
      const matchesRevenue =
        !("annualRevenue" in item) ||
        (item.annualRevenue >= filters.minRevenue &&
          item.annualRevenue <= filters.maxRevenue);

      // Deal amount range filter
      const matchesDealAmount =
        !("amount" in item) ||
        (item.amount >= filters.minDealAmount &&
          item.amount <= filters.maxDealAmount);

      // Lead score filter
      const matchesLeadScore =
        filters.leadScores.length === 0 ||
        !("leadScore" in item) ||
        filters.leadScores.includes(item.leadScore);

      return (
        matchesSearch &&
        matchesDataType &&
        matchesIndustry &&
        matchesCountry &&
        matchesLifecycleStage &&
        matchesDealStage &&
        matchesOwner &&
        matchesCompanySize &&
        matchesActivityType &&
        matchesRevenue &&
        matchesDealAmount &&
        matchesLeadScore
      );
    });

    // Apply sorting
    filtered.sort((a, b) => {
      let aValue: any, bValue: any;

      switch (sort.field) {
        case "lastActivityDate":
          aValue = "lastActivityDate" in a ? a.lastActivityDate : "";
          bValue = "lastActivityDate" in b ? b.lastActivityDate : "";
          break;
        case "createdDate":
          aValue = "createdDate" in a ? a.createdDate : "";
          bValue = "createdDate" in b ? b.createdDate : "";
          break;
        case "leadScore":
          aValue = "leadScore" in a ? a.leadScore : 0;
          bValue = "leadScore" in b ? b.leadScore : 0;
          break;
        case "amount":
          aValue = "amount" in a ? a.amount : 0;
          bValue = "amount" in b ? b.amount : 0;
          break;
        case "annualRevenue":
          aValue = "annualRevenue" in a ? a.annualRevenue : 0;
          bValue = "annualRevenue" in b ? b.annualRevenue : 0;
          break;
        case "name":
          aValue =
            "name" in a
              ? a.name
              : "firstName" in a
                ? `${a.firstName} ${a.lastName}`
                : "";
          bValue =
            "name" in b
              ? b.name
              : "firstName" in b
                ? `${b.firstName} ${b.lastName}`
                : "";
          break;
        default:
          aValue = "";
          bValue = "";
      }

      if (sort.direction === "asc") {
        return aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
      } else {
        return aValue > bValue ? -1 : aValue < bValue ? 1 : 0;
      }
    });

    return filtered;
  }, [data, filters, sort]);

  // Debounced search effect
  const handleSearch = useCallback(() => {
    onSearch(filteredData, filters, sort);
  }, [filteredData, filters, sort, onSearch]);

  React.useEffect(() => {
    const timeoutId = setTimeout(handleSearch, 300);
    return () => clearTimeout(timeoutId);
  }, [handleSearch]);

  const handleFilterChange = (key: keyof SearchFilters, value: any) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const handleSortChange = (field: string) => {
    setSort((prev) => ({
      field,
      direction:
        prev.field === field && prev.direction === "desc" ? "asc" : "desc",
    }));
  };

  const clearFilters = () => {
    setFilters({
      searchQuery: "",
      dataType: dataType,
      industries: [],
      countries: [],
      lifecycleStages: [],
      dealStages: [],
      leadScores: [],
      dateRange: { start: "", end: "" },
      owners: [],
      companySizes: [],
      minRevenue: 0,
      maxRevenue: 10000000,
      minDealAmount: 0,
      maxDealAmount: 10000000,
      activityTypes: [],
    });
  };

  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.600");

  return (
    <Box
      bg={bgColor}
      border="1px"
      borderColor={borderColor}
      borderRadius="lg"
      p={4}
    >
      <VStack spacing={4} align="stretch">
        {/* Search Header */}
        <HStack justify="space-between">
          <Text fontSize="lg" fontWeight="semibold">
            HubSpot Search
          </Text>
          <HStack>
            <Button
              size="sm"
              variant="outline"
              leftIcon={<FiFilter />}
              onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
            >
              {showAdvancedFilters ? "Hide Filters" : "Show Filters"}
            </Button>
            <Button size="sm" variant="ghost" onClick={clearFilters}>
              Clear All
            </Button>
          </HStack>
        </HStack>

        {/* Main Search Input */}
        <InputGroup>
          <InputLeftElement pointerEvents="none">
            <SearchIcon color="gray.400" />
          </InputLeftElement>
          <Input
            placeholder="Search contacts, companies, deals, activities..."
            value={filters.searchQuery}
            onChange={(e) => handleFilterChange("searchQuery", e.target.value)}
          />
        </InputGroup>

        {/* Quick Filters */}
        <HStack spacing={4} flexWrap="wrap">
          <Select
            size="sm"
            width="auto"
            value={filters.dataType}
            onChange={(e) =>
              handleFilterChange("dataType", e.target.value as HubSpotDataType)
            }
          >
            <option value="all">All Data</option>
            <option value="contacts">Contacts</option>
            <option value="companies">Companies</option>
            <option value="deals">Deals</option>
            <option value="activities">Activities</option>
          </Select>

          <Select
            size="sm"
            width="auto"
            value={sort.field}
            onChange={(e) => handleSortChange(e.target.value)}
          >
            <option value="lastActivityDate">Sort by Last Activity</option>
            <option value="createdDate">Sort by Created Date</option>
            <option value="leadScore">Sort by Lead Score</option>
            <option value="amount">Sort by Deal Amount</option>
            <option value="annualRevenue">Sort by Revenue</option>
            <option value="name">Sort by Name</option>
          </Select>

          <Badge colorScheme={sort.direction === "desc" ? "blue" : "gray"}>
            {sort.direction === "desc" ? "↓ Desc" : "↑ Asc"}
          </Badge>
        </HStack>

        {/* Active Filters */}
        {(filters.industries.length > 0 ||
          filters.countries.length > 0 ||
          filters.lifecycleStages.length > 0 ||
          filters.dealStages.length > 0) && (
          <HStack spacing={2} flexWrap="wrap">
            <Text fontSize="sm" color="gray.600">
              Active filters:
            </Text>
            {filters.industries.map((industry) => (
              <Tag key={industry} size="sm" colorScheme="blue">
                <TagLabel>Industry: {industry}</TagLabel>
                <TagCloseButton
                  onClick={() =>
                    handleFilterChange(
                      "industries",
                      filters.industries.filter((i) => i !== industry),
                    )
                  }
                />
              </Tag>
            ))}
            {filters.countries.map((country) => (
              <Tag key={country} size="sm" colorScheme="green">
                <TagLabel>Country: {country}</TagLabel>
                <TagCloseButton
                  onClick={() =>
                    handleFilterChange(
                      "countries",
                      filters.countries.filter((c) => c !== country),
                    )
                  }
                />
              </Tag>
            ))}
            {filters.lifecycleStages.map((stage) => (
              <Tag key={stage} size="sm" colorScheme="purple">
                <TagLabel>Stage: {stage}</TagLabel>
                <TagCloseButton
                  onClick={() =>
                    handleFilterChange(
                      "lifecycleStages",
                      filters.lifecycleStages.filter((s) => s !== stage),
                    )
                  }
                />
              </Tag>
            ))}
            {filters.dealStages.map((stage) => (
              <Tag key={stage} size="sm" colorScheme="orange">
                <TagLabel>Deal Stage: {stage}</TagLabel>
                <TagCloseButton
                  onClick={() =>
                    handleFilterChange(
                      "dealStages",
                      filters.dealStages.filter((s) => s !== stage),
                    )
                  }
                />
              </Tag>
            ))}
          </HStack>
        )}

        {/* Advanced Filters */}
        {showAdvancedFilters && (
          <Box border="1px" borderColor={borderColor} borderRadius="md" p={4}>
            <Grid
              templateColumns="repeat(auto-fit, minmax(200px, 1fr))"
              gap={4}
            >
              {/* Industry Filter */}
              <GridItem>
                <Text fontSize="sm" fontWeight="medium" mb={2}>
                  Industry
                </Text>
                <CheckboxGroup
                  value={filters.industries}
                  onChange={(values) =>
                    handleFilterChange("industries", values)
                  }
                >
                  <VStack align="start" spacing={1}>
                    {filterOptions.industries.slice(0, 5).map((industry) => (
                      <Checkbox key={industry} value={industry} size="sm">
                        {industry}
                      </Checkbox>
                    ))}
                  </VStack>
                </CheckboxGroup>
              </GridItem>

              {/* Country Filter */}
              <GridItem>
                <Text fontSize="sm" fontWeight="medium" mb={2}>
                  Country
                </Text>
                <CheckboxGroup
                  value={filters.countries}
                  onChange={(values) => handleFilterChange("countries", values)}
                >
                  <VStack align="start" spacing={1}>
                    {filterOptions.countries.slice(0, 5).map((country) => (
                      <Checkbox key={country} value={country} size="sm">
                        {country}
                      </Checkbox>
                    ))}
                  </VStack>
                </CheckboxGroup>
              </GridItem>

              {/* Lifecycle Stage Filter */}
              <GridItem>
                <Text fontSize="sm" fontWeight="medium" mb={2}>
                  Lifecycle Stage
                </Text>
                <CheckboxGroup
                  value={filters.lifecycleStages}
                  onChange={(values) =>
                    handleFilterChange("lifecycleStages", values)
                  }
                >
                  <VStack align="start" spacing={1}>
                    {filterOptions.lifecycleStages.map((stage) => (
                      <Checkbox key={stage} value={stage} size="sm">
                        {stage}
                      </Checkbox>
                    ))}
                  </VStack>
                </CheckboxGroup>
              </GridItem>

              {/* Deal Stage Filter */}
              <GridItem>
                <Text fontSize="sm" fontWeight="medium" mb={2}>
                  Deal Stage
                </Text>
                <CheckboxGroup
                  value={filters.dealStages}
                  onChange={(values) =>
                    handleFilterChange("dealStages", values)
                  }
                >
                  <VStack align="start" spacing={1}>
                    {filterOptions.dealStages.map((stage) => (
                      <Checkbox key={stage} value={stage} size="sm">
                        {stage}
                      </Checkbox>
                    ))}
                  </VStack>
                </CheckboxGroup>
              </GridItem>

              {/* Owner Filter */}
              <GridItem>
                <Text fontSize="sm" fontWeight="medium" mb={2}>
                  Owner
                </Text>
                <CheckboxGroup
                  value={filters.owners}
                  onChange={(values) => handleFilterChange("owners", values)}
                >
                  <VStack align="start" spacing={1}>
                    {filterOptions.owners.slice(0, 5).map((owner) => (
                      <Checkbox key={owner} value={owner} size="sm">
                        {owner}
                      </Checkbox>
                    ))}
                  </VStack>
                </CheckboxGroup>
              </GridItem>

              {/* Company Size Filter */}
              <GridItem>
                <Text fontSize="sm" fontWeight="medium" mb={2}>
                  Company Size
                </Text>
                <CheckboxGroup
                  value={filters.companySizes}
                  onChange={(values) =>
                    handleFilterChange("companySizes", values)
                  }
                >
                  <VStack align="start" spacing={1}>
                    {filterOptions.companySizes.map((size) => (
                      <Checkbox key={size} value={size} size="sm">
                        {size}
                      </Checkbox>
                    ))}
                  </VStack>
                </CheckboxGroup>
              </GridItem>

              {/* Activity Type Filter */}
              <GridItem>
                <Text fontSize="sm" fontWeight="medium" mb={2}>
                  Activity Type
                </Text>
                <CheckboxGroup
                  value={filters.activityTypes}
                  onChange={(values) =>
                    handleFilterChange("activityTypes", values)
                  }
                >
                  <VStack align="start" spacing={1}>
                    {filterOptions.activityTypes.map((type) => (
                      <Checkbox key={type} value={type} size="sm">
                        {type}
                      </Checkbox>
                    ))}
                  </VStack>
                </CheckboxGroup>
              </GridItem>

              {/* Revenue Range Filter */}
              <GridItem>
                <Text fontSize="sm" fontWeight="medium" mb={2}>
                  Annual Revenue Range
                </Text>
                <HStack spacing={2}>
                  <Input
                    size="sm"
                    placeholder="Min"
                    type="number"
                    value={filters.minRevenue}
                    onChange={(e) =>
                      handleFilterChange("minRevenue", Number(e.target.value))
                    }
                  />
                  <Text fontSize="sm">to</Text>
                  <Input
                    size="sm"
                    placeholder="Max"
                    type="number"
                    value={filters.maxRevenue}
                    onChange={(e) =>
                      handleFilterChange("maxRevenue", Number(e.target.value))
                    }
                  />
                </HStack>
              </GridItem>

              {/* Deal Amount Range Filter */}
              <GridItem>
                <Text fontSize="sm" fontWeight="medium" mb={2}>
                  Deal Amount Range
                </Text>
                <HStack spacing={2}>
                  <Input
                    size="sm"
                    placeholder="Min"
                    type="number"
                    value={filters.minDealAmount}
                    onChange={(e) =>
                      handleFilterChange(
                        "minDealAmount",
                        Number(e.target.value),
                      )
                    }
                  />
                  <Text fontSize="sm">to</Text>
                  <Input
                    size="sm"
                    placeholder="Max"
                    type="number"
                    value={filters.maxDealAmount}
                    onChange={(e) =>
                      handleFilterChange(
                        "maxDealAmount",
                        Number(e.target.value),
                      )
                    }
                  />
                </HStack>
              </GridItem>

              {/* Lead Score Filter */}
              <GridItem>
                <Text fontSize="sm" fontWeight="medium" mb={2}>
                  Lead Score
                </Text>
                <CheckboxGroup
                  value={filters.leadScores}
                  onChange={(values) =>
                    handleFilterChange("leadScores", values.map(Number))
                  }
                >
                  <HStack spacing={2}>
                    {[1, 2, 3, 4, 5].map((score) => (
                      <Checkbox key={score} value={score.toString()} size="sm">
                        {score}+
                      </Checkbox>
                    ))}
                  </HStack>
                </CheckboxGroup>
              </GridItem>
            </Grid>
          </Box>
        )}

        {/* Results Summary */}
        <HStack justify="space-between">
          <Text fontSize="sm" color="gray.600">
            {loading ? (
              <HStack>
                <Spinner size="sm" />
                <Text>Searching...</Text>
              </HStack>
            ) : (
              `Showing ${filteredData.length} of ${totalCount} results`
            )}
          </Text>
          <Badge colorScheme="blue" fontSize="sm">
            {filters.dataType.toUpperCase()}
          </Badge>
        </HStack>

        {/* Search Results Preview */}
        {!loading && filteredData.length > 0 && (
          <Box
            maxH="200px"
            overflowY="auto"
            border="1px"
            borderColor={borderColor}
            borderRadius="md"
            p={2}
          >
            <VStack spacing={1} align="stretch">
              {filteredData.slice(0, 10).map((item, index) => (
                <Box
                  key={`${item.id}-${index}`}
                  p={2}
                  borderBottom="1px"
                  borderColor={borderColor}
                >
                  <HStack justify="space-between">
                    <Text fontSize="sm" fontWeight="medium">
                      {"firstName" in item
                        ? `${item.firstName} ${item.lastName}`
                        : "name" in item
                          ? item.name
                          : "subject" in item
                            ? item.subject
                            : "Unknown"}
                    </Text>
                    <Badge
                      size="sm"
                      colorScheme={
                        "leadScore" in item && item.leadScore >= 4
                          ? "green"
                          : "stage" in item
                            ? "blue"
                            : "engagementType" in item
                              ? "purple"
                              : "gray"
                      }
                    >
                      {"leadScore" in item
                        ? `Score: ${item.leadScore}`
                        : "stage" in item
                          ? item.stage
                          : "engagementType" in item
                            ? item.engagementType
                            : "industry" in item
                              ? item.industry
                              : "Contact"}
                    </Badge>
                  </HStack>
                  <Text fontSize="xs" color="gray.600">
                    {"email" in item
                      ? item.email
                      : "domain" in item
                        ? item.domain
                        : "amount" in item
                          ? `$${item.amount.toLocaleString()}`
                          : "body" in item
                            ? item.body.substring(0, 50) + "..."
                            : ""}
                  </Text>
                </Box>
              ))}
              {filteredData.length > 10 && (
                <Text fontSize="xs" color="gray.500" textAlign="center" p={2}>
                  ... and {filteredData.length - 10} more results
                </Text>
              )}
            </VStack>
          </Box>
        )}

        {!loading && filteredData.length === 0 && filters.searchQuery && (
          <Text fontSize="sm" color="gray.500" textAlign="center" p={4}>
            No results found for &quot;{filters.searchQuery}&quot;
          </Text>
        )}
      </VStack>
    </Box>
  );
};

export default HubSpotSearch;
