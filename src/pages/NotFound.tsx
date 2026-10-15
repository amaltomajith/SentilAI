import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Sprite } from "@/components/pixel/Sprite";

const NotFound = () => (
  <div className="grid min-h-[100dvh] place-items-center px-4 text-center">
    <div>
      <Sprite name="skull" size={88} className="mx-auto" />
      <h1 className="mt-6 text-4xl font-semibold tracking-tightest">Nothing here.</h1>
      <p className="mt-3 text-muted-foreground">That page does not exist, or it moved.</p>
      <Button asChild className="mt-8"><Link to="/">Back to Sentinel</Link></Button>
    </div>
  </div>
);

export default NotFound;