test('probe', () => {
  console.log('typeof getItem:', typeof (localStorage as any).getItem);
  console.log('is mock fn:', (localStorage as any).getItem?.mockReturnValue !== undefined);
  (localStorage.getItem as any)?.mockReturnValue?.('tok');
  console.log('after set, getItem() ->', (localStorage as any).getItem());
});
