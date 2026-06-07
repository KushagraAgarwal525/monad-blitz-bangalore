"use client";

import * as Tabs from "@radix-ui/react-tabs";
import { cn } from "@/lib/utils";

export const TabsRoot = Tabs.Root;
export const TabsList = ({ className, ...props }: React.ComponentProps<typeof Tabs.List>) => (
  <Tabs.List className={cn("inline-flex h-9 items-center rounded-lg bg-zinc-100 p-1", className)} {...props} />
);
export const TabsTrigger = ({ className, ...props }: React.ComponentProps<typeof Tabs.Trigger>) => (
  <Tabs.Trigger
    className={cn(
      "inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium data-[state=active]:bg-white data-[state=active]:shadow",
      className
    )}
    {...props}
  />
);
export const TabsContent = Tabs.Content;
