/**
 * Canvas Component Marketplace Gallery
 *
 * Browse, search, and install components from the marketplace.
 */

'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Search, Star, Download, Eye, DollarSign, Filter, TrendingUp } from 'lucide-react';
import { ComponentDetailModal } from './ComponentDetailModal';

// Types
interface CanvasComponent {
  id: string;
  name: string;
  description: string;
  category: string;
  component_type: string;
  tags: string[];
  version: string;
  thumbnail_url?: string;
  preview_url?: string;
  demo_url?: string;
  price: number;
  currency: string;
  is_free: boolean;
  is_featured: boolean;
  license: string;
  author_id: string;
  installs: number;
  downloads: number;
  views: number;
  rating: number;
  rating_count: number;
  created_at: string;
  updated_at: string;
}

interface MarketplaceResponse {
  components: CanvasComponent[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

interface Category {
  name: string;
  count: number;
}

interface Tag {
  name: string;
  count: number;
}

// API service
class MarketplaceService {
  private baseUrl = '/api/canvas-marketplace';

  async browse(params: {
    query?: string;
    category?: string;
    tags?: string;
    component_type?: string;
    min_price?: number;
    max_price?: number;
    is_free?: boolean;
    is_featured?: boolean;
    sort_by?: string;
    sort_order?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<MarketplaceResponse> {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    });

    const response = await fetch(`${this.baseUrl}/components?${searchParams}`);
    if (!response.ok) throw new Error('Failed to fetch marketplace components');

    return response.json();
  }

  async getComponent(componentId: string): Promise<CanvasComponent> {
    const response = await fetch(`${this.baseUrl}/components/${componentId}`);
    if (!response.ok) throw new Error('Failed to fetch component details');

    return response.json();
  }

  async installComponent(componentId: string, canvasId?: string): Promise<any> {
    const response = await fetch(`${this.baseUrl}/components/install`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ component_id: componentId, canvas_id: canvasId }),
    });

    if (!response.ok) throw new Error('Failed to install component');

    return response.json();
  }

  async rateComponent(componentId: string, rating: number, review?: string): Promise<any> {
    const response = await fetch(`${this.baseUrl}/components/${componentId}/rate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rating, review }),
    });

    if (!response.ok) throw new Error('Failed to rate component');

    return response.json();
  }

  async getCategories(): Promise<{ categories: Category[] }> {
    const response = await fetch(`${this.baseUrl}/categories`);
    if (!response.ok) throw new Error('Failed to fetch categories');

    return response.json();
  }

  async getTags(): Promise<{ tags: Tag[] }> {
    const response = await fetch(`${this.baseUrl}/tags`);
    if (!response.ok) throw new Error('Failed to fetch tags');

    return response.json();
  }
}

const marketplaceService = new MarketplaceService();

// Component Card
interface ComponentCardProps {
  component: CanvasComponent;
  onInstall: (component: CanvasComponent) => void;
  onView: (component: CanvasComponent) => void;
}

function ComponentCard({ component, onInstall, onView }: ComponentCardProps) {
  return (
    <Card className="overflow-hidden hover:shadow-lg transition-shadow">
      {component.thumbnail_url && (
        <div className="relative h-48 bg-gray-100 cursor-pointer" onClick={() => onView(component)}>
          <img
            src={component.thumbnail_url}
            alt={component.name}
            className="w-full h-full object-cover"
          />
          {component.is_featured && (
            <Badge className="absolute top-2 right-2 bg-yellow-500">
              <TrendingUp className="w-3 h-3 mr-1" />
              Featured
            </Badge>
          )}
          {component.is_free && (
            <Badge className="absolute top-2 left-2 bg-green-500">Free</Badge>
          )}
        </div>
      )}

      <CardHeader>
        <div className="flex justify-between items-start">
          <CardTitle className="text-lg">{component.name}</CardTitle>
          <div className="flex items-center gap-1 text-sm">
            <Star className="w-4 h-4 fill-yellow-400 text-yellow-400" />
            <span className="font-semibold">{component.rating.toFixed(1)}</span>
            <span className="text-gray-500">({component.rating_count})</span>
          </div>
        </div>
        <CardDescription className="line-clamp-2">{component.description}</CardDescription>
      </CardHeader>

      <CardContent>
        <div className="flex flex-wrap gap-1 mb-3">
          {component.tags.slice(0, 3).map((tag) => (
            <Badge key={tag} variant="secondary" className="text-xs">
              {tag}
            </Badge>
          ))}
          <Badge variant="outline" className="text-xs">
            {component.category}
          </Badge>
        </div>

        <div className="flex items-center justify-between text-sm text-gray-600">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <Download className="w-4 h-4" />
              {component.installs}
            </span>
            <span className="flex items-center gap-1">
              <Eye className="w-4 h-4" />
              {component.views}
            </span>
          </div>

          {!component.is_free && (
            <span className="flex items-center gap-1 font-semibold text-green-600">
              <DollarSign className="w-4 h-4" />
              {component.price.toFixed(2)}
            </span>
          )}
        </div>
      </CardContent>

      <CardFooter className="flex gap-2">
        <Button variant="outline" className="flex-1" onClick={() => onView(component)}>
          Preview
        </Button>
        <Button className="flex-1" onClick={() => onInstall(component)}>
          Install
        </Button>
      </CardFooter>
    </Card>
  );
}

// Main Marketplace Gallery
export function MarketplaceGallery() {
  const [components, setComponents] = useState<CanvasComponent[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasMore, setHasMore] = useState(false);
  const [total, setTotal] = useState(0);

  // Modal state
  const [selectedComponent, setSelectedComponent] = useState<CanvasComponent | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [sortBy, setSortBy] = useState('created_at');
  const [isFreeOnly, setIsFreeOnly] = useState(false);
  const [isFeaturedOnly, setIsFeaturedOnly] = useState(false);

  // Metadata
  const [categories, setCategories] = useState<Category[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);

  // Fetch components
  const fetchComponents = async (offset = 0) => {
    try {
      setLoading(true);
      const data = await marketplaceService.browse({
        query: searchQuery || undefined,
        category: selectedCategory || undefined,
        tags: selectedTags.length > 0 ? selectedTags.join(',') : undefined,
        sort_by: sortBy,
        sort_order: 'desc',
        is_free: isFreeOnly || undefined,
        is_featured: isFeaturedOnly || undefined,
        limit: 20,
        offset,
      });

      if (offset === 0) {
        setComponents(data.components);
      } else {
        setComponents((prev) => [...prev, ...data.components]);
      }

      setTotal(data.total);
      setHasMore(data.has_more);
    } catch (error) {
      console.error('Failed to fetch components:', error);
    } finally {
      setLoading(false);
    }
  };

  // Fetch metadata
  useEffect(() => {
    const fetchMetadata = async () => {
      try {
        const [catsData, tagsData] = await Promise.all([
          marketplaceService.getCategories(),
          marketplaceService.getTags(),
        ]);

        setCategories(catsData.categories);
        setTags(tagsData.tags);
      } catch (error) {
        console.error('Failed to fetch metadata:', error);
      }
    };

    fetchMetadata();
  }, []);

  // Fetch on filter change
  useEffect(() => {
    fetchComponents(0);
  }, [searchQuery, selectedCategory, selectedTags, sortBy, isFreeOnly, isFeaturedOnly]);

  // Handlers
  const handleInstall = async (component: CanvasComponent) => {
    try {
      await marketplaceService.installComponent(component.id);
      alert(`${component.name} installed successfully!`);
    } catch (error) {
      console.error('Failed to install component:', error);
      alert('Failed to install component');
    }
  };

  const handleView = (component: CanvasComponent) => {
    setSelectedComponent(component);
    setIsModalOpen(true);
  };

  const handleLoadMore = () => {
    fetchComponents(components.length);
  };

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  return (
    <div className="container mx-auto py-8 px-4">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2">Canvas Component Marketplace</h1>
        <p className="text-gray-600">
          Browse and install components created by the community
        </p>
      </div>

      {/* Search & Filters */}
      <div className="mb-6 space-y-4">
        <div className="flex gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <Input
              placeholder="Search components..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>

          <Select value={selectedCategory} onValueChange={setSelectedCategory}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Category" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Categories</SelectItem>
              {categories.map((cat) => (
                <SelectItem key={cat.name} value={cat.name}>
                  {cat.name} ({cat.count})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="created_at">Newest</SelectItem>
              <SelectItem value="rating">Top Rated</SelectItem>
              <SelectItem value="installs">Most Installed</SelectItem>
              <SelectItem value="price">Price: Low to High</SelectItem>
              <SelectItem value="name">Name: A-Z</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Filter toggles */}
        <div className="flex gap-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={isFreeOnly}
              onChange={(e) => setIsFreeOnly(e.target.checked)}
              className="rounded"
            />
            <span className="text-sm">Free only</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={isFeaturedOnly}
              onChange={(e) => setIsFeaturedOnly(e.target.checked)}
              className="rounded"
            />
            <span className="text-sm">Featured only</span>
          </label>
        </div>

        {/* Tag filters */}
        {selectedTags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {selectedTags.map((tag) => (
              <Badge key={tag} variant="default" className="cursor-pointer" onClick={() => toggleTag(tag)}>
                {tag} ×
              </Badge>
            ))}
          </div>
        )}

        {/* Popular tags */}
        <div className="flex flex-wrap gap-2">
          <span className="text-sm text-gray-600">Popular:</span>
          {tags.slice(0, 10).map((tag) => (
            <Badge
              key={tag.name}
              variant={selectedTags.includes(tag.name) ? 'default' : 'outline'}
              className="cursor-pointer"
              onClick={() => toggleTag(tag.name)}
            >
              {tag.name}
            </Badge>
          ))}
        </div>
      </div>

      {/* Results */}
      <div className="mb-4">
        <p className="text-sm text-gray-600">
          {total} {total === 1 ? 'component' : 'components'} found
        </p>
      </div>

      {loading && components.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-600">Loading components...</p>
        </div>
      ) : components.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-600">No components found. Try adjusting your filters.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {components.map((component) => (
              <ComponentCard
                key={component.id}
                component={component}
                onInstall={handleInstall}
                onView={handleView}
              />
            ))}
          </div>

          {hasMore && (
            <div className="mt-8 text-center">
              <Button onClick={handleLoadMore} disabled={loading}>
                {loading ? 'Loading...' : 'Load More'}
              </Button>
            </div>
          )}
        </>
      )}

      {/* Component Detail Modal */}
      <ComponentDetailModal
        component={selectedComponent}
        open={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onInstall={handleInstall}
      />
    </div>
  );
}

export default MarketplaceGallery;
