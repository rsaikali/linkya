import numpy as np, os
os.environ["TF_CPP_MIN_LOG_LEVEL"]="3"
import keras
from keras import layers
from lab import *
def features(x,hc,ref):
    """x: (B,W) watts; hc:(B,W); ref:(B,) heater reference level -> (B,W,3)"""
    xn=np.clip(x/ref[:,None],-0.5,3.0)
    dx=np.clip(np.diff(xn,axis=1,prepend=xn[:,:1]),-1.5,1.5)
    return np.stack([xn,hc,dx*3],-1).astype(np.float32)
def build(ch=64,dil=(1,2,4,8,16,32,64,128,256),k=3):
    inp=keras.Input((None,3)); h=layers.Conv1D(ch,1)(inp); skips=[]
    for d in dil:
        a=layers.Conv1D(ch,k,dilation_rate=d,padding="same",activation="tanh")(h)
        b=layers.Conv1D(ch,k,dilation_rate=d,padding="same",activation="sigmoid")(h)
        z=layers.Multiply()([a,b]); r=layers.Conv1D(ch,1)(z); skips.append(layers.Conv1D(ch,1)(z)); h=layers.Add()([h,r])
    s=layers.Activation("relu")(layers.Add()(skips)); s=layers.Conv1D(ch,1,activation="relu")(s)
    st=layers.Conv1D(1,1,activation="sigmoid",name="state")(s)
    pw=layers.Conv1D(1,1,activation="relu",name="power")(s)
    return keras.Model(inp,[st,pw])
def gen(n,seed,train=True):
    e=Engine(seed,train); X=np.zeros((n,W,3),np.float32); S=np.zeros((n,W,1),np.float32); P=np.zeros((n,W,1),np.float32)
    rng=np.random.default_rng(seed+99)
    for i in range(n):
        nd=int(rng.integers(0,9)); fh=[0,1,1,2,2][int(rng.integers(5))]
        x,st,tg,hc,v=e.make(n_dis=nd,force_heater=fh)
        ref=np.array([HREF*v*(1+rng.normal(0,0.010))]); X[i]=features(x[None],hc[None],ref)[0]
        S[i,:,0]=st; P[i,:,0]=tg/HREF
    return X,S,P
if __name__=="__main__":
    import time,sys
    N=int(sys.argv[1]); EP=int(sys.argv[2])
    t=time.time(); X,S,P=gen(N,1,True); Xv,Sv,Pv=gen(max(N//6,300),2,False); print("gen",round(time.time()-t),"s; heater frac",S.mean().round(3),flush=True)
    m=build(); print("params",m.count_params())
    m.compile(optimizer=keras.optimizers.Adam(2e-3),loss={"state":"binary_crossentropy","power":keras.losses.Huber(0.1)},loss_weights={"state":1.0,"power":2.0},metrics={"state":[keras.metrics.AUC(name="auc"),keras.metrics.Precision(name="p"),keras.metrics.Recall(name="r")]})
    cb=[keras.callbacks.ReduceLROnPlateau(patience=2,factor=0.5,verbose=1),keras.callbacks.ModelCheckpoint(sys.argv[3],save_best_only=True,monitor="val_loss")]
    m.fit(X,{"state":S,"power":P},validation_data=(Xv,{"state":Sv,"power":Pv}),epochs=EP,batch_size=16,callbacks=cb,verbose=2)
