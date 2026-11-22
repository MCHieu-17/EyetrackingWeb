# k6 summary

scenario: samples

- http_req_waiting: avg=17.522, min=5.315, med=14.552, max=47.474, p(90)=28.642, p(95)=30.622, p(99)=46.281
- vus: min=5.000, max=5.000
- http_req_duration{expected_response:true}: min=5.410, med=14.941, max=47.578, p(90)=28.849, p(95)=30.793, p(99)=46.415, avg=17.704
- iterations: count=230.000, rate=22.863
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_sending: avg=0.036, min=0.005, med=0.039, max=0.071, p(90)=0.053, p(95)=0.057, p(99)=0.069
- http_req_failed: rate=0.000
- http_req_receiving: min=0.020, med=0.095, max=1.560, p(90)=0.305, p(95)=0.370, p(99)=0.610, avg=0.146
- http_req_blocked: min=0.002, med=0.011, max=0.171, p(90)=0.015, p(95)=0.023, p(99)=0.116, avg=0.013
- http_req_duration: med=14.941, max=47.578, p(90)=28.849, p(95)=30.793, p(99)=46.415, avg=17.704, min=5.410
- http_req_connecting: p(99)=0.072, avg=0.002, min=0.000, med=0.000, max=0.144, p(90)=0.000, p(95)=0.000
