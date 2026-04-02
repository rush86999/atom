'use client';

import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Star, Download, Eye, DollarSign, Code, Settings, Tag, Package, Shield, TrendingUp } from 'lucide-react';

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
  code?: string;
  config_schema?: any;
  dependencies?: string[];
  css_dependencies?: string[];
  created_at: string;
  updated_at: string;
  recent_ratings?: Array<{
    id: string;
    rating: number;
    review: string;
    helpful_count: number;
    created_at: string;
  }>;
}

interface ComponentDetailModalProps {
  component: CanvasComponent | null;
  open: boolean;
  onClose: () => void;
  onInstall: (component: CanvasComponent) => void;
}

export function ComponentDetailModal({
  component,
  open,
  onClose,
  onInstall
}: ComponentDetailModalProps) {
  if (!component) return null;

  const handleInstall = () => {
    onInstall(component);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <DialogTitle className="text-2xl mb-2">{component.name}</DialogTitle>
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <div className="flex items-center gap-1">
                  <Star className="w-4 h-4 fill-yellow-400 text-yellow-400" />
                  <span className="font-semibold">{component.rating.toFixed(1)}</span>
                  <span>({component.rating_count})</span>
                </div>
                <span>{component.installs} installs</span>
                <span>v{component.version}</span>
              </div>
            </div>
            <div className="flex gap-2">
              {component.is_featured && (
                <Badge className="bg-yellow-500">
                  <TrendingUp className="w-3 h-3 mr-1" />
                  Featured
                </Badge>
              )}
              {component.is_free ? (
                <Badge className="bg-green-500">Free</Badge>
              ) : (
                <Badge className="bg-blue-500">
                  <DollarSign className="w-3 h-3 mr-1" />
                  {component.price.toFixed(2)}
                </Badge>
              )}
            </div>
          </div>
        </DialogHeader>

        <Tabs defaultValue="overview" className="mt-4">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="details">Details</TabsTrigger>
            <TabsTrigger value="reviews">Reviews</TabsTrigger>
            <TabsTrigger value="install">Install</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            {component.thumbnail_url && (
              <div className="rounded-lg overflow-hidden">
                <img
                  src={component.thumbnail_url}
                  alt={component.name}
                  className="w-full h-auto"
                />
              </div>
            )}

            <div>
              <h3 className="font-semibold mb-2">Description</h3>
              <p className="text-gray-700">{component.description}</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="flex items-center gap-2">
                <Package className="w-5 h-5 text-gray-500" />
                <div>
                  <p className="text-sm text-gray-500">Category</p>
                  <p className="font-medium">{component.category}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Code className="w-5 h-5 text-gray-500" />
                <div>
                  <p className="text-sm text-gray-500">Type</p>
                  <p className="font-medium">{component.component_type}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-gray-500" />
                <div>
                  <p className="text-sm text-gray-500">License</p>
                  <p className="font-medium">{component.license}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Download className="w-5 h-5 text-gray-500" />
                <div>
                  <p className="text-sm text-gray-500">Installs</p>
                  <p className="font-medium">{component.installs}</p>
                </div>
              </div>
            </div>

            {component.tags && component.tags.length > 0 && (
              <div>
                <h3 className="font-semibold mb-2 flex items-center gap-2">
                  <Tag className="w-4 h-4" />
                  Tags
                </h3>
                <div className="flex flex-wrap gap-2">
                  {component.tags.map((tag) => (
                    <Badge key={tag} variant="secondary">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </TabsContent>

          <TabsContent value="details" className="space-y-4">
            <div>
              <h3 className="font-semibold mb-2">Version Information</h3>
              <div className="bg-gray-50 p-4 rounded-lg">
                <p><strong>Version:</strong> {component.version}</p>
                <p><strong>Updated:</strong> {new Date(component.updated_at).toLocaleDateString()}</p>
                <p><strong>Created:</strong> {new Date(component.created_at).toLocaleDateString()}</p>
              </div>
            </div>

            {component.dependencies && component.dependencies.length > 0 && (
              <div>
                <h3 className="font-semibold mb-2">Dependencies</h3>
                <ul className="list-disc list-inside space-y-1 text-sm">
                  {component.dependencies.map((dep, idx) => (
                    <li key={idx} className="text-gray-700">{dep}</li>
                  ))}
                </ul>
              </div>
            )}

            {component.demo_url && (
              <div>
                <h3 className="font-semibold mb-2">Demo</h3>
                <a
                  href={component.demo_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  View Live Demo →
                </a>
              </div>
            )}
          </TabsContent>

          <TabsContent value="reviews" className="space-y-4">
            <div className="flex items-center gap-4 mb-4">
              <div className="text-4xl font-bold">{component.rating.toFixed(1)}</div>
              <div>
                <div className="flex items-center gap-1">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <Star
                      key={star}
                      className={`w-5 h-5 ${
                        star <= Math.round(component.rating)
                          ? 'fill-yellow-400 text-yellow-400'
                          : 'text-gray-300'
                      }`}
                    />
                  ))}
                </div>
                <p className="text-sm text-gray-600">{component.rating_count} reviews</p>
              </div>
            </div>

            {component.recent_ratings && component.recent_ratings.length > 0 ? (
              <div className="space-y-4">
                {component.recent_ratings.map((review) => (
                  <div key={review.id} className="border-b pb-4">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="flex items-center gap-1">
                        {[1, 2, 3, 4, 5].map((star) => (
                          <Star
                            key={star}
                            className={`w-4 h-4 ${
                              star <= review.rating
                                ? 'fill-yellow-400 text-yellow-400'
                                : 'text-gray-300'
                            }`}
                          />
                        ))}
                      </div>
                      <span className="text-sm text-gray-500">
                        {new Date(review.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    {review.review && (
                      <p className="text-gray-700">{review.review}</p>
                    )}
                    <div className="flex items-center gap-2 mt-2 text-sm text-gray-500">
                      <span>{review.helpful_count} helpful</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-center py-8">No reviews yet</p>
            )}
          </TabsContent>

          <TabsContent value="install" className="space-y-4">
            <div>
              <h3 className="font-semibold mb-2">Installation</h3>
              <p className="text-gray-700 mb-4">
                Install this component to your canvas. You'll be able to configure it after installation.
              </p>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                <p className="text-sm text-blue-800">
                  <strong>Note:</strong> This component requires the {component.component_type} component type.
                  Make sure your canvas supports it before installing.
                </p>
              </div>

              <Button onClick={handleInstall} className="w-full" size="lg">
                <Download className="w-5 h-5 mr-2" />
                Install {component.name}
              </Button>
            </div>

            {component.price > 0 && (
              <div className="border-t pt-4">
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Price</span>
                  <span className="text-2xl font-bold text-green-600">
                    ${component.price.toFixed(2)}
                  </span>
                </div>
                <p className="text-sm text-gray-500 mt-2">
                  One-time purchase. Lifetime updates included.
                </p>
              </div>
            )}
          </TabsContent>
        </Tabs>

        <div className="flex gap-2 mt-4 pt-4 border-t">
          <Button variant="outline" className="flex-1" onClick={onClose}>
            Close
          </Button>
          <Button className="flex-1" onClick={handleInstall}>
            <Download className="w-4 h-4 mr-2" />
            Install
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
