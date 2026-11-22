# k6 summary

scenario: aoi_summary

- vus: min=2.000, max=2.000
- iterations: count=52.000, rate=5.073
- http_req_blocked: avg=0.015, min=0.003, med=0.011, max=0.110, p(90)=0.015, p(95)=0.032, p(99)=0.098
- http_req_receiving: avg=0.234, min=0.088, med=0.201, max=0.725, p(90)=0.354, p(95)=0.515, p(99)=0.652
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_waiting: p(90)=223.020, p(95)=227.431, p(99)=238.957, avg=192.946, min=172.981, med=190.350, max=239.495
- http_req_connecting: avg=0.003, min=0.000, med=0.000, max=0.082, p(90)=0.000, p(95)=0.000, p(99)=0.072
- http_req_failed: rate=0.000
- http_req_sending: p(99)=0.235, avg=0.058, min=0.011, med=0.052, max=0.392, p(90)=0.067, p(95)=0.078
- http_req_duration: med=190.579, max=239.743, p(90)=223.286, p(95)=227.707, p(99)=239.173, avg=193.239, min=173.165
- http_req_duration{expected_response:true}: avg=193.239, min=173.165, med=190.579, max=239.743, p(90)=223.286, p(95)=227.707, p(99)=239.173
