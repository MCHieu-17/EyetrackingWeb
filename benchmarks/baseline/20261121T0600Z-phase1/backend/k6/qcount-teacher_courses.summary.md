# k6 summary

scenario: teacher_courses

- http_req_duration: p(99)=48.796, avg=39.492, min=18.053, med=42.475, max=49.304, p(90)=46.175, p(95)=46.766
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: avg=39.492, min=18.053, med=42.475, max=49.304, p(90)=46.175, p(95)=46.766, p(99)=48.796
- http_req_waiting: avg=39.399, min=17.986, med=42.381, max=49.215, p(90)=46.088, p(95)=46.639, p(99)=48.700
- iterations: count=20.000, rate=4.160
- http_req_blocked: max=0.233, p(90)=0.013, p(95)=0.024, p(99)=0.191, avg=0.021, min=0.003, med=0.011
- http_req_receiving: med=0.043, max=0.059, p(90)=0.055, p(95)=0.058, p(99)=0.059, avg=0.044, min=0.031
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- vus: min=1.000, max=1.000
- http_req_sending: max=0.217, p(90)=0.063, p(95)=0.090, p(99)=0.191, avg=0.049, min=0.012, med=0.042
- http_req_connecting: p(90)=0.000, p(95)=0.004, p(99)=0.070, avg=0.004, min=0.000, med=0.000, max=0.086
