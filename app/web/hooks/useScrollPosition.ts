import { useRef } from "react";

interface UseScrollPositionOptions {
  key: string;
}

export function useScrollPosition({ key }: UseScrollPositionOptions) {
  const scrollPositionRef = useRef<number>(0);

  // 保存滚动位置
  const saveScrollPosition = () => {
    scrollPositionRef.current = window.scrollY;
    sessionStorage.setItem(key, scrollPositionRef.current.toString());
  };

  // 恢复滚动位置
  const restoreScrollPosition = () => {
    const savedPosition = sessionStorage.getItem(key);
    if (savedPosition) {
      const position = parseInt(savedPosition, 10);
      window.scrollTo(0, position);
      scrollPositionRef.current = position;
    }
  };

  return { saveScrollPosition, restoreScrollPosition };
}
