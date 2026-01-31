import React, { useState, useMemo, useCallback } from "react";
import { Search, X, Filter } from "lucide-react";
import { Input } from "../../ui/input";
import { Button } from "../../ui/button";
import { Badge } from "../../ui/badge";
import { Checkbox } from "../../ui/checkbox";
import { Spinner } from "../../ui/spinner";
import { Card, CardContent } from "../../ui/card";

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

  return (
    <Card className="w-full">
      <CardContent className="p-4 space-y-4">
        {/* Search Header */}
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            HubSpot Search
          </h3>
          <div className="flex space-x-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
            >
              <Filter className="mr-2 h-4 w-4" />
              {showAdvancedFilters ? "Hide Filters" : "Show Filters"}
            </Button>
            <Button size="sm" variant="ghost" onClick={clearFilters}>
              Clear All
            </Button>
          </div>
        </div>

        {/* Main Search Input */}
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="h-4 w-4 text-gray-400" />
          </div>
          <Input
            className="pl-10"
            placeholder="Search contacts, companies, deals, activities..."
            value={filters.searchQuery}
            onChange={(e) => handleFilterChange("searchQuery", e.target.value)}
          />
        </div>

        {/* Quick Filters */}
        <div className="flex flex-wrap gap-4 items-center">
          <select
            className="h-9 w-auto rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
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
          </select>

          <select
            className="h-9 w-auto rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
            value={sort.field}
            onChange={(e) => handleSortChange(e.target.value)}
          >
            <option value="lastActivityDate">Sort by Last Activity</option>
            <option value="createdDate">Sort by Created Date</option>
            <option value="leadScore">Sort by Lead Score</option>
            <option value="amount">Sort by Deal Amount</option>
            <option value="annualRevenue">Sort by Revenue</option>
            <option value="name">Sort by Name</option>
          </select>

          <Badge variant={sort.direction === "desc" ? "default" : "secondary"}>
            {sort.direction === "desc" ? "↓ Desc" : "↑ Asc"}
          </Badge>
        </div>

        {/* Active Filters */}
        {(filters.industries.length > 0 ||
          filters.countries.length > 0 ||
          filters.lifecycleStages.length > 0 ||
          filters.dealStages.length > 0) && (
            <div className="flex flex-wrap gap-2 items-center">
              <span className="text-sm text-gray-500">
                Active filters:
              </span>
              {filters.industries.map((industry) => (
                <Badge key={industry} variant="secondary" className="flex items-center gap-1">
                  Industry: {industry}
                  <X
                    className="h-3 w-3 cursor-pointer hover:text-red-500"
                    onClick={() =>
                      handleFilterChange(
                        "industries",
                        filters.industries.filter((i) => i !== industry),
                      )
                    }
                  />
                </Badge>
              ))}
              {filters.countries.map((country) => (
                <Badge key={country} variant="outline" className="flex items-center gap-1 border-green-200 bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-300 dark:border-green-800">
                  Country: {country}
                  <X
                    className="h-3 w-3 cursor-pointer hover:text-red-500"
                    onClick={() =>
                      handleFilterChange(
                        "countries",
                        filters.countries.filter((c) => c !== country),
                      )
                    }
                  />
                </Badge>
              ))}
              {filters.lifecycleStages.map((stage) => (
                <Badge key={stage} variant="outline" className="flex items-center gap-1 border-purple-200 bg-purple-50 text-purple-700 dark:bg-purple-900/20 dark:text-purple-300 dark:border-purple-800">
                  Stage: {stage}
                  <X
                    className="h-3 w-3 cursor-pointer hover:text-red-500"
                    onClick={() =>
                      handleFilterChange(
                        "lifecycleStages",
                        filters.lifecycleStages.filter((s) => s !== stage),
                      )
                    }
                  />
                </Badge>
              ))}
              {filters.dealStages.map((stage) => (
                <Badge key={stage} variant="outline" className="flex items-center gap-1 border-orange-200 bg-orange-50 text-orange-700 dark:bg-orange-900/20 dark:text-orange-300 dark:border-orange-800">
                  Deal Stage: {stage}
                  <X
                    className="h-3 w-3 cursor-pointer hover:text-red-500"
                    onClick={() =>
                      handleFilterChange(
                        "dealStages",
                        filters.dealStages.filter((s) => s !== stage),
                      )
                    }
                  />
                </Badge>
              ))}
            </div>
          )}

        {/* Advanced Filters */}
        {showAdvancedFilters && (
          <div className="border border-gray-200 dark:border-gray-700 rounded-md p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Industry Filter */}
              <div>
                <p className="text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                  Industry
                </p>
                <div className="space-y-1">
                  {filterOptions.industries.slice(0, 5).map((industry) => (
                    <div key={industry} className="flex items-center space-x-2">
                      <Checkbox
                        id={`industry-${industry}`}
                        checked={filters.industries.includes(industry)}
                        onCheckedChange={(checked: boolean) => {
                          const newIndustries = checked
                            ? [...filters.industries, industry]
                            : filters.industries.filter((i) => i !== industry);
                          handleFilterChange("industries", newIndustries);
                        }}
                      />
                      <label htmlFor={`industry-${industry}`} className="text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
                        {industry}
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Country Filter */}
              <div>
                <p className="text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                  Country
                </p>
                <div className="space-y-1">
                  {filterOptions.countries.slice(0, 5).map((country) => (
                    <div key={country} className="flex items-center space-x-2">
                      <Checkbox
                        id={`country-${country}`}
                        checked={filters.countries.includes(country)}
                        onCheckedChange={(checked: boolean) => {
                          const newCountries = checked
                            ? [...filters.countries, country]
                            : filters.countries.filter((c) => c !== country);
                          handleFilterChange("countries", newCountries);
                        }}
                      />
                      <label htmlFor={`country-${country}`} className="text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
                        {country}
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Lifecycle Stage Filter */}
              <div>
                <p className="text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                  Lifecycle Stage
                </p>
                <div className="space-y-1">
                  {filterOptions.lifecycleStages.map((stage) => (
                    <div key={stage} className="flex items-center space-x-2">
                      <Checkbox
                        id={`stage-${stage}`}
                        checked={filters.lifecycleStages.includes(stage)}
                        onCheckedChange={(checked: boolean) => {
                          const newStages = checked
                            ? [...filters.lifecycleStages, stage]
                            : filters.lifecycleStages.filter((s) => s !== stage);
                          handleFilterChange("lifecycleStages", newStages);
                        }}
                      />
                      <label htmlFor={`stage-${stage}`} className="text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
                        {stage}
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Deal Stage Filter */}
              <div>
                <p className="text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                  Deal Stage
                </p>
                <div className="space-y-1">
                  {filterOptions.dealStages.map((stage) => (
                    <div key={stage} className="flex items-center space-x-2">
                      <Checkbox
                        id={`deal-stage-${stage}`}
                        checked={filters.dealStages.includes(stage)}
                        onCheckedChange={(checked: boolean) => {
                          const newStages = checked
                            ? [...filters.dealStages, stage]
                            : filters.dealStages.filter((s) => s !== stage);
                          handleFilterChange("dealStages", newStages);
                        }}
                      />
                      <label htmlFor={`deal-stage-${stage}`} className="text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
                        {stage}
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Owner Filter */}
              <div>
                <p className="text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                  Owner
                </p>
                <div className="space-y-1">
                  {filterOptions.owners.slice(0, 5).map((owner) => (
                    <div key={owner} className="flex items-center space-x-2">
                      <Checkbox
                        id={`owner-${owner}`}
                        checked={filters.owners.includes(owner)}
                        onCheckedChange={(checked: boolean) => {
                          const newOwners = checked
                            ? [...filters.owners, owner]
                            : filters.owners.filter((o) => o !== owner);
                          handleFilterChange("owners", newOwners);
                        }}
                      />
                      <label htmlFor={`owner-${owner}`} className="text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
                        {owner}
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Company Size Filter */}
              <div>
                <p className="text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                  Company Size
                </p>
                <div className="space-y-1">
                  {filterOptions.companySizes.map((size) => (
                    <div key={size} className="flex items-center space-x-2">
                      <Checkbox
                        id={`size-${size}`}
                        checked={filters.companySizes.includes(size)}
                        onCheckedChange={(checked: boolean) => {
                          const newSizes = checked
                            ? [...filters.companySizes, size]
                            : filters.companySizes.filter((s) => s !== size);
                          handleFilterChange("companySizes", newSizes);
                        }}
                      />
                      <label htmlFor={`size-${size}`} className="text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
                        {size}
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Activity Type Filter */}
              <div>
                <p className="text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                  Activity Type
                </p>
                <div className="space-y-1">
                  {filterOptions.activityTypes.map((type) => (
                    <div key={type} className="flex items-center space-x-2">
                      <Checkbox
                        id={`type-${type}`}
                        checked={filters.activityTypes.includes(type)}
                        onCheckedChange={(checked: boolean) => {
                          const newTypes = checked
                            ? [...filters.activityTypes, type]
                            : filters.activityTypes.filter((t) => t !== type);
                          handleFilterChange("activityTypes", newTypes);
                        }}
                      />
                      <label htmlFor={`type-${type}`} className="text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
                        {type}
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Revenue Range Filter */}
              <div>
                <p className="text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                  Annual Revenue Range
                </p>
                <div className="flex items-center space-x-2">
                  <Input
                    className="h-8 text-sm"
                    placeholder="Min"
                    type="number"
                    value={filters.minRevenue}
                    onChange={(e) =>
                      handleFilterChange("minRevenue", Number(e.target.value))
                    }
                  />
                  <span className="text-sm text-gray-500">to</span>
                  <Input
                    className="h-8 text-sm"
                    placeholder="Max"
                    type="number"
                    value={filters.maxRevenue}
                    onChange={(e) =>
                      handleFilterChange("maxRevenue", Number(e.target.value))
                    }
                  />
                </div>
              </div>

              {/* Deal Amount Range Filter */}
              <div>
                <p className="text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                  Deal Amount Range
                </p>
                <div className="flex items-center space-x-2">
                  <Input
                    className="h-8 text-sm"
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
                  <span className="text-sm text-gray-500">to</span>
                  <Input
                    className="h-8 text-sm"
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
                </div>
              </div>

              {/* Lead Score Filter */}
              <div>
                <p className="text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                  Lead Score
                </p>
                <div className="flex items-center space-x-4">
                  {[1, 2, 3, 4, 5].map((score) => (
                    <div key={score} className="flex items-center space-x-1">
                      <Checkbox
                        id={`score-${score}`}
                        checked={filters.leadScores.includes(score)}
                        onCheckedChange={(checked: boolean) => {
                          const newScores = checked
                            ? [...filters.leadScores, score]
                            : filters.leadScores.filter((s) => s !== score);
                          handleFilterChange("leadScores", newScores);
                        }}
                      />
                      <label htmlFor={`score-${score}`} className="text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
                        {score}+
                      </label>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Results Summary */}
        <div className="flex justify-between items-center">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            {loading ? (
              <div className="flex items-center space-x-2">
                <Spinner size="sm" />
                <span>Searching...</span>
              </div>
            ) : (
              `Showing ${filteredData.length} of ${totalCount} results`
            )}
          </div>
          <Badge variant="default">
            {filters.dataType.toUpperCase()}
          </Badge>
        </div>

        {/* Search Results Preview */}
        {!loading && filteredData.length > 0 && (
          <div className="max-h-[200px] overflow-y-auto border border-gray-200 dark:border-gray-700 rounded-md p-2">
            <div className="space-y-1">
              {filteredData.slice(0, 10).map((item, index) => (
                <div key={index} className="p-2 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md">
                  {/* Render item details based on type - simplified for preview */}
                  <div className="font-medium text-sm">
                    {"name" in item ? item.name : "firstName" in item ? `${item.firstName} ${item.lastName}` : item.subject}
                  </div>
                  <div className="text-xs text-gray-500">
                    {"company" in item ? (item.company as React.ReactNode) : "engagementType" in item ? (item.engagementType as React.ReactNode) : ""}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {!loading && filteredData.length === 0 && filters.searchQuery && (
          <div className="text-sm text-gray-500 text-center p-4">
            No results found for &quot;{filters.searchQuery}&quot;
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default HubSpotSearch;
